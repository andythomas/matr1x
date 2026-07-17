# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
Defines a system for automatically defining an elabFTW entry for a successful measurement.

This module provides functionality to create and manage entries in the
elabFTW electronic lab notebook system.
"""

import difflib
import logging
import re
from pathlib import Path

import elabapi_python
from elabapi_python.rest import ApiException
from jinja2 import Template
from pydantic import BaseModel, Field

from matr1x.models import Message
from matr1x.system import MergedSystem, System

logger = logging.getLogger(__name__)


class ElabConfig(BaseModel):
    """Configuration parameters for elabFTW system."""

    # Sensitive configuration (will be moved to sensitive_config)
    host: str | None = Field(None, description="URL of the elabFTW server (REQUIRED)")
    api_key: str | None = Field(None, description="API key for elabFTW (REQUIRED)")
    teamid: int = Field(0, description="Team ID for elabFTW")

    # Non-sensitive configuration
    debug: bool = False
    enable_elab: bool = True
    require_server: bool = False
    upload_datafile: bool | int = False
    create_resource: bool = False
    category: str = Field("", description="Category for experiments")
    resource_category: str = Field("", description="Category for resources")
    title_template: str = """
        {%- set title_parts = [] %}
        {%- if dcdata['identifier'] %}
            {%- set _ = title_parts.append(dcdata['identifier']) %}
        {%- endif %}
        {%- set _ = title_parts.append(base_filename) %}
        {{- title_parts | join(' - ') -}}
    """
    body_template: str = """
        <h1>Measurement Report</h1>
        <p><strong>{{ dcdata['source'] }}</strong></p>
        <hr>
        <p><strong>Filename:</strong> {{ filename }}</p>
        <p><strong>Sample:</strong> {{ dcdata['identifier'] }}</p>
        <p><strong>Creator:</strong> {{ dcdata['creator'] }}</p>
        <h2>Description:</h2>
        <p>{{ dcdata['description'] | replace('\n', '<br>') }}</p>
        <h2>Additional Data:</h2>
        <table>
            <tr>
                <th>Parameter</th>
                <th>Value</th>
            </tr>
            {%- for key, value in dcdata.items() %}
            {%- if key not in ['identifier', 'creator', 'description', 'source'] %}
            <tr>
                <td>{{ key }}</td>
                <td>{{ value }}</td>
            </tr>
            {%- endif %}
            {%- endfor %}
        </table>
    """


def _is_template_content(template: str) -> bool:
    """Check if string contains template content rather than a file path.

    Parameters
    ----------
    template : str
        The string to check.

    Returns
    -------
    bool
        True if the string appears to be template content, False otherwise.
    """
    # Check for excessive length (filesystem limits)
    if len(template) > 255:
        return True

    # Check for Jinja2 template syntax and newlines
    template_patterns = ["{%", "{{", "{#", "%}", "}}", "#}", "\n"]
    return any(pattern in template for pattern in template_patterns)


# ============================
# This area contains the required system definition and
# the optional reimplementation of the set and reset function
# ============================
class Elab(System):
    """
    System for interfacing with elabFTW electronic lab notebook.

    This class provides functionality to create experiment entries,
    attach files, add tags and link resources in an elabFTW instance.
    """

    def __init__(self):
        super().__init__()
        self.merged_system: MergedSystem
        # clean meta data for this system
        for key in self.dcdata:
            self.dcdata[key] = ""

        # Load configuration from files and separate sensitive from non-sensitive config
        self.load_config(
            ElabConfig,
            "matr1x.systems.system_elabftw",
            sensitive_keys=["host", "api_key", "teamid"],
        )

        self._team_id = getattr(self.sensitive_config, "teamid", 0)

        # predefine api client
        self.api_client = None
        # internal variables to queue things for upload
        self._attachments = {}
        self._tags = []
        self._resources = {}

    def set(self, *args, **kwargs):
        """
        Initialize the server connection and resource and create if requested.

        The resource will be linked to the experiment entry generated
        during reset.
        """
        super().set(*args, **kwargs)
        if not self.config.enable_elab:
            return
        configuration = elabapi_python.Configuration()

        if not getattr(self.sensitive_config, "host", None) or not getattr(
            self.sensitive_config, "api_key", None
        ):
            self.report(
                Message(
                    "ElabFTW connection host or API key not found in the TOML config, make "
                    "sure host address and API key of the server are specified."
                )
            )
            raise Exception(
                "ElabFTW host or API key not found in the TOML config, make sure "
                "host address and API key of the server are specified."
            )

        configuration.api_key["api_key"] = self.sensitive_config.api_key
        configuration.api_key_prefix["api_key"] = "Authorization"
        configuration.host = self.sensitive_config.host + "/api/v2"
        configuration.debug = self.config.debug
        configuration.verify_ssl = True

        # create an instance of the API class
        self.api_client = elabapi_python.ApiClient(configuration)
        # fix issue with Authorization header not being proberly set by the generated lib
        self.api_client.set_default_header(
            header_name="Authorization", header_value=self.sensitive_config.api_key
        )
        # test server connection by a harmless read-only query
        try:
            info_client = elabapi_python.InfoApi(self.api_client)
            info_client.get_info()
        except Exception:
            if self.config.require_server:
                self.report(
                    Message(
                        "ElabFTW connection could not be established "
                        "but is configured to be required."
                    )
                )
                raise Exception("ElabFTW connection could not be established")
            else:
                self.report(
                    Message(
                        "ElabFTW connection could not be established\n"
                        "no labbook entry will be created, but we continue."
                    )
                )
                # disable api_client for rest of run to be more smooth
                self.api_client = None
        for key in ["identifier", "relation"]:
            # add resource link to sample specified in identifier and relation
            samplename = self.merged_system.dcdata[key]
            if not samplename:
                continue
            try:
                self.add_resource(samplename)
            except Exception:
                pass
            if self.config.create_resource and samplename not in self._resources:
                # need to create the resource
                resource_id = self._create_resource(samplename)
                self._resources[samplename] = resource_id

    def add_tag(self, name: str) -> None:
        """
        Queue a tag to be added to the created experiment.

        Parameters
        ----------
        name
            If such a tag does not exist it will be created.
        """
        self._tags.append(name)

    def add_attachment(self, filename: Path | str, label: str = "") -> None:
        """
        Queue additional file for upload to the labbook entry.

        The file is then uploaded during the reset function.

        Parameters
        ----------
        filename
            The name of the file to be attached.
        label
            A label or description for the attachment.
        """
        self._attachments[str(filename)] = label

    def add_resource(self, resource: str) -> None:
        """
        Queue a resource to be linked to the created experiment.

        Parameters
        ----------
        resource
            The name of the resource to be linked.

        Notes
        -----
        This method searches for a resource with the given name and, if found,
        queues it to be linked to the experiment entry that will be created.
        If multiple resources are found with the same name, no linking occurs.
        """
        resource_id = self._search_resource(resource)
        if resource_id:
            self._resources[resource] = resource_id

    def conditional_add_file(self):
        """Attach the filename but only if allowed by configuration."""
        if self.config.upload_datafile and self.filename:
            file_size_mb = self.filename.stat().st_size / (1024 * 1024)
            if (
                isinstance(self.config.upload_datafile, bool)
                or file_size_mb <= self.config.upload_datafile
            ):
                self.add_attachment(self.filename, "Data file")
            else:
                self.report(
                    Message(f"File size ({file_size_mb:.2f} MB) exceeds the limit. Not uploading.")
                )

    def _render_template(self, template: str) -> str:
        """
        Render a template string or file using Jinja2.

        This method takes a template (either a string or a file path) and renders it
        using Jinja2, with the current filename and merged system data as context.

        Parameters
        ----------
        template
            Either a template string or a path to a template file.

        Returns
        -------
        str
            The rendered template string.

        Notes
        -----
        If the template is a file path, the method will read the contents of the file
        before rendering. The template has access to the `filename` and `dcdata` variables
        in its context.
        """
        if _is_template_content(template):
            template_str = template
        else:
            try:  # use try/except around file operations that can fail
                if Path(template).is_file():
                    with Path(template).open() as file:
                        template_str = file.read()
                else:
                    template_str = template
            except OSError:
                template_str = template
        jinjatemplate = Template(template_str)
        return jinjatemplate.render(
            base_filename=self.filename.name if self.filename else "",
            filename=self.filename,
            dcdata=self.merged_system.dcdata,
            query=self.merged_system.query_dict,
        )

    def _determine_userid(self) -> int | None:
        """
        Fetch the elabFTW userid from the user given in metadata.

        Returns
        -------
        int or None
            The user ID if found, None otherwise.
        """
        if not self.api_client:
            return None
        userApi = elabapi_python.UsersApi(self.api_client)
        try:
            response = userApi.read_users()
        except ApiException as e:
            self.report(Message(f"Exception when calling UsersApi->readUsers: {e}\n"))
            return None

        names = [user["fullname"] for user in response]
        # Handle potential None values in orgid safely
        orgids = [str(user["orgid"]).lower() if user["orgid"] else None for user in response]

        search_string = self.merged_system.dcdata.get("creator")
        if not search_string:
            return None

        search_string_lower = search_string.lower()

        # Step 1: try to match orgid
        try:
            idx = orgids.index(search_string_lower)
            return response[idx]["userid"]
        except (ValueError, KeyError):
            pass

        # Step 2: try to find exact substring matches
        substring_matches = [name for name in names if search_string_lower in name.lower()]

        # Step 3: Match logic
        most_likely_match = None
        if substring_matches:
            most_likely_match = substring_matches[0]
        else:
            closest_matches = difflib.get_close_matches(search_string, names, n=1, cutoff=0.6)
            most_likely_match = closest_matches[0] if closest_matches else None

        if most_likely_match:
            return response[names.index(most_likely_match)]["userid"]

        return None

    def _determine_category(self) -> int | None:
        """
        Determine Experiment Category ID to use.

        Returns
        -------
        int or None
            The category ID if found, None otherwise.
        """
        if not self.api_client:
            return None
        catApi = elabapi_python.ExperimentsCategoriesApi(self.api_client)
        category_name = getattr(self.config, "category", None)
        if not category_name:
            return None
        try:
            response = catApi.read_team_experiments_categories(self._team_id)
            # find id for search category
            return next((item.id for item in response if item.title == category_name), None)
        except ApiException as e:
            self.report(
                Message(
                    "Exception during ExperimentsCategoriesApi->"
                    f"readTeamExperimentsCategories: {e}\n"
                )
            )
            return None

    def _determine_status(self, status: str) -> int | None:
        """
        Determine status id for the measurement status.

        Parameters
        ----------
        status
            The status string to look up.

        Returns
        -------
        int or None
            The status ID if found, None otherwise.
        """
        if not self.api_client:
            return None
        expstatusApi = elabapi_python.ExperimentsStatusApi(self.api_client)
        try:
            response = expstatusApi.read_team_experiments_status(self._team_id)
        except ApiException as e:
            self.report(
                Message(
                    f"Exception when calling ExperimentsStatusApi->readTeamExperimentsStatus: {e}\n"
                )
            )
            return None
        return next((item.id for item in response if item.title == status), None)

    def _determine_resource_category(self) -> int | None:
        """
        Determine resource category id from the name.

        Returns
        -------
        int or None
            The resource category ID if found, None otherwise.
        """
        if not self.api_client:
            return None
        category_name = getattr(self.config, "resource_category", None)
        if not category_name:
            return None

        itemsTypesApi = elabapi_python.ItemsTypesResourcesTemplatesApi(self.api_client)
        try:
            # Read all resources categories that are accessible.
            response = itemsTypesApi.read_items_types()
        except ApiException as e:
            self.report(
                Message(
                    "Exception when calling ItemsTypesResourcesTemplatesApi->"
                    f"read_item_types: {e}\n"
                )
            )
            return None
        # find id for search category
        return next((item.id for item in response if item.title == category_name), None)

    def _create_resource(self, name: str) -> int | None:
        """
        Create a new resource in elabFTW.

        This method creates a new resource with the given name and the category
        specified in the configuration.

        Parameters
        ----------
        name
            The name of the resource to be created.

        Returns
        -------
        int or None
            The ID of the newly created resource.

        Raises
        ------
        ValueError
            If a valid resource category could not be found.

        Notes
        -----
        This method requires a valid resource category to be specified in the
        configuration. If not found, it will raise a ValueError.
        """
        if not self.api_client:
            return None
        resource_cat = self._determine_resource_category()
        if not resource_cat:
            raise ValueError("Valid resource category could not be found, but is needed.")
        # create an instance of the API class
        itemsApi = elabapi_python.ItemsApi(self.api_client)
        body = {"category_id": resource_cat}

        item_id = None
        try:
            response = itemsApi.post_item_with_http_info(body=body)
            locationHeaderInResponse = response[2].get("Location")
            item_id = int(locationHeaderInResponse.split("/").pop())
            itemsApi.patch_item(body={"title": name}, id=item_id)
            self.report(Message(f"created ElabFTW resource with name {name}"))
        except ApiException as e:
            self.report(Message(f"Exception when calling ItemsApi: {e}\n"))
        if item_id is None:
            raise ValueError("Failed to create resource - itemId is None")
        return item_id

    def _search_resource(self, resource: str) -> int | None:
        """
        Search resource id corresponding to the resource name.

        Parameters
        ----------
        resource
            Name of the resource to obtain the ID for.

        Returns
        -------
        int or None
            The resource ID if found, None otherwise.
        """
        if not resource or not self.api_client:
            return None
        itemsApi = elabapi_python.ItemsApi(self.api_client)
        try:
            response = itemsApi.read_items(q=f"'{resource}'")
        except ApiException as e:
            self.report(Message(f"Exception when calling ItemsApi->readItems: {e}\n"))
            return None
        if item_id := next((item.id for item in response if item.title == resource), None):
            return item_id
        else:
            self.report(
                Message(
                    f"Could not identify ElabFTW resource corresponding to the name {resource}"
                )
            )
        return None

    def _parse_tags_from_line(self, line: str) -> list | None:
        """
        Parse tags from line, tags are marked with #.

        Parameters
        ----------
        line
            Line from which to parse the tags.

        Returns
        -------
        list or None
            Returns a list with parsed tags, otherwise None
        """
        if not line:
            return
        if "#" not in line:
            return
        pattern = r"#(?:\(([^)]+)\)|(\S+))"
        matches = re.findall(pattern, line)

        # Extract matched hashtags
        hashtags = [match[0] if match[0] else match[1] for match in matches]
        return hashtags

    def elab_post_experiment(self, status: str, reset_tags: bool = True) -> None:
        """
        Create a new experiment in elabFTW.

        This function will render the jinja template strings and upload queued attachments.

        Parameters
        ----------
        status
            Status string which will be attempted to set also in elabFTW.
        reset_tags
            Controls whether tags are reset after experiment is posted
        """
        if not self.config.enable_elab or not self.api_client:
            return

        title = self._render_template(self.config.title_template)
        body = self._render_template(self.config.body_template)

        if self.merged_system.dcdata["description"]:
            additional_tags = self._parse_tags_from_line(
                self.merged_system.dcdata["description"].splitlines()[0]
            )
            if additional_tags:
                for tag in additional_tags:
                    self.add_tag(tag)

        experiments_api = elabapi_python.ExperimentsApi(self.api_client)

        title = self._handle_existing_title(experiments_api, title)

        params = {
            "title": title,
            "body": body,
        }

        userid = self._determine_userid()
        if userid:
            params["userid"] = userid

        catid = self._determine_category()
        if catid:
            params["category"] = catid

        status_id = self._determine_status(status)
        if status_id is not None:
            params["status"] = status_id

        try:
            create_body = {"tags": self._tags}
            response_body, status_code, response_headers = (
                experiments_api.post_experiment_with_http_info(body=create_body)
            )

            if reset_tags:
                self._tags = []

            experiment_id = response_headers["Location"].split("/")[-1]

            experiments_api.patch_experiment(id=experiment_id, body=params)

            self._upload_attachments(experiment_id)
            self._link_resources(experiment_id)

        except ApiException as e:
            self.report(Message(f"Exception with post or patch experiment: {e}\n"))

    def _handle_existing_title(self, experiments_api, title):
        """Handle title when experiment with the same title already exists."""
        try:
            api_response = experiments_api.read_experiments(q=f"'{title}'")
        except ApiException as e:
            self.report(Message(f"Exception when calling ExperimentsApi->readExperiments: {e}\n"))
            return title

        if not isinstance(api_response, list) or len(api_response) == 0:
            return title

        n = 0
        titles = [entry.title for entry in api_response]
        for existing_title in titles:
            if existing_title.endswith(title):
                n += 1

        if n == 0:
            return title

        newtitle = f"{n:03d}: {title}"
        while newtitle in titles:
            n += 1
            newtitle = f"{n:03d}: {title}"
        return newtitle

    def _upload_attachments(self, experiment_id: str) -> None:
        """Upload attachments to the specified experiment."""
        if not self._attachments:
            return

        uploads_api = elabapi_python.UploadsApi(self.api_client)
        for file, comment in self._attachments.items():
            uploads_api.post_upload("experiments", experiment_id, file=file, comment=comment)
        self._attachments = {}

    def _link_resources(self, experiment_id: str) -> None:
        """Link resources to the specified experiment."""
        if not self._resources:
            return

        links_api = elabapi_python.LinksToItemsApi(self.api_client)
        for resource_id in self._resources.values():
            links_api.post_entity_items_links("experiments", experiment_id, resource_id)

    def _backup_info(self, status: str) -> None:
        """
        Print essential info in case of upload error.

        Parameters
        ----------
        status
            Status of the experiment to print.
        """
        logger.exception("Detailed error message:")
        backup_info = (
            "some error occured during creation of lab book entry.\n"
            "see log file for details.\n"
            "Here some information to create the labbook entry manually:"
        )
        self.report(Message(backup_info))
        title = self._render_template(self.config.title_template)
        body = self._render_template(self.config.body_template)
        category_name = self.config.get("category", None)
        entry_info = f"Entry title: {title}\n"
        if category_name:
            entry_info += f"Category: {category_name}\n"
        entry_info += f"Content (in html): {body}\n---- End Content ----"
        self.report(Message(entry_info))

        if self._attachments:
            attach_msg = "Attach files: \n"
            attach_msg += "\n".join(
                f"{file}: {comment}" for file, comment in self._attachments.items()
            )
            self.report(Message(attach_msg))
        if self._tags:
            self.report(Message(f"Set tags: {self._tags}"))
        if self._resources:
            self.report(Message(f"Link Resources: {self._resources.keys()}"))
        if status:
            self.report(Message(f"Set experiment status: {status}"))

    def reset(self, *args, **kwargs):
        """
        Handle deinitializiation of the measurement.

        Called by matrix when measurement is complete. Creates elabFTW
        entry if measurement was successful.
        """
        # if measurement was not unsuccessful a elab entry is generated
        if "status" not in kwargs or kwargs["status"] != "aborted":
            self.conditional_add_file()
            if self.filename:
                # only create measurement if there is a datafile
                try:
                    self.elab_post_experiment(kwargs.get("status", ""))
                except Exception:
                    self._backup_info(kwargs.get("status", ""))
            else:
                self.report(Message("no measurement file exists, not creating entry"))
        super().reset(*args, **kwargs)
        # reset internal variables to enable reuse of a class instance
        self._attachments = {}
        self._tags = []
        self._resources = {}


# ============================
# initialize system
system = Elab()
