"""
Defines a system for automatically defining an elabFTW entry for a successful measurement.

This module provides functionality to create and manage entries in the elabFTW
electronic lab notebook system.
"""

import difflib
import logging
import os
import re
from typing import Optional

import elabapi_python
from elabapi_python.rest import ApiException
from jinja2 import Template

from matr1x import get_config_dict
from matr1x.system import System

logger = logging.getLogger(__name__)


# ============================
# This area contains the required MeasSystem definition and
# the optional reimplementation of the set and reset function
# ============================
class ElabSystem(System):
    """
    System for interfacing with elabFTW electronic lab notebook.

    This class provides functionality to create experiment entries, attach files,
    add tags and link resources in an elabFTW instance.
    """

    def __init__(self):
        super().__init__()
        # clean meta data for this system
        for key in self.dcdata:
            self.dcdata[key] = ""
        # load API key and host from config file
        # In ~/.matrix.toml or in a local file matrix.toml there must be
        # [matr1x.systems.system_elabftw]
        # host = "HOST"  # without api/v2 end, only URL (with port)
        # api_key = "API_KEY"
        # teamid = 0  # optional team ID
        #
        # Sensitive information (host, api_key, teamid) will be stored in
        # sensitive_config and will NOT appear in file headers.
        #
        # additional config entries are optional.
        # These include "debug", "upload_datafile", "category", "body_template", "title_template",
        # "create_resource", "resource_category"
        # see the code for their use and meaning.

        # Non-sensitive configuration
        self.config = {
            "debug": False,
            "enable_elab": True,  # boolean flag to decide about entry creation
            "require_server": False,  # boolean to decide if server is required
            "upload_datafile": False,  # boolean or maximal file size in MB
            "create_resource": False,  # if sample Identifier can not be found a resource entry can be created
            "resource_category": None,  # category for newly generated resources.
            "title_template": """
                {%- set title_parts = [] %}
                {%- if dcdata['identifier'] %}
                    {%- set _ = title_parts.append(dcdata['identifier']) %}
                {%- endif %}
                {%- set _ = title_parts.append(base_filename) %}
                {{- title_parts | join(' - ') -}}
            """,
            "body_template": """
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
            """,  # the template strings can also refer to filenames.
        }

        # Sensitive configuration (will not be stored in file headers)
        self.sensitive_config = {
            "host": None,
            "api_key": None,
            "teamid": 0,
        }

        # Load configuration from files
        config_data = get_config_dict("matr1x.systems.system_elabftw")

        # Separate sensitive from non-sensitive config
        for key, value in config_data.items():
            if key in self.sensitive_config.keys():
                self.sensitive_config[key] = value
            else:
                self.config[key] = value

        self._team_id = self.sensitive_config.get("teamid", 0)

        # predefine api client
        self.api_client = None
        # internal variables to queue things for upload
        self._attachments = {}
        self._tags = []
        self._resources = {}

    def set(self, *args, **kwargs):
        """
        Initialize the server connection and resource and create if requested.

        The resource will be linked to the experiment entry generated during reset.
        """
        super().set(*args, **kwargs)
        if not self.config["enable_elab"]:
            return
        configuration = elabapi_python.Configuration()
        try:
            configuration.api_key["api_key"] = self.sensitive_config["api_key"]
            configuration.api_key_prefix["api_key"] = "Authorization"
            configuration.host = self.sensitive_config["host"] + "/api/v2"
            configuration.debug = self.config["debug"]
        except KeyError:
            print(
                "ElabFTW connection API key not found in the TOML config, make "
                "sure api_key and host address of the server are specified."
            )
            raise Exception(
                "ElabFTW API key not found in the TOML config, make sure "
                "api_key and host address of the server are specified."
            )
        configuration.verify_ssl = True

        # create an instance of the API class
        self.api_client = elabapi_python.ApiClient(configuration)
        # fix issue with Authorization header not being proberly set by the generated lib
        self.api_client.set_default_header(
            header_name="Authorization", header_value=self.sensitive_config["api_key"]
        )
        # test server connection by a harmless read-only query
        try:
            info_client = elabapi_python.InfoApi(self.api_client)
            info_client.get_info()
        except Exception:
            if self.config["require_server"]:
                print(
                    "ElabFTW connection could not be established but is configured to be required."
                )
                raise Exception("ElabFTW connection could not be established")
            else:
                print("ElabFTW connection could not be established")
                print("no labbook entry will be created, but we continue.")
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
            if self.config.get("create_resource") and samplename not in self._resources:
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

    def add_attachment(self, filename: str, label: str = "") -> None:
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
        self._attachments[filename] = label

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
        if self.config["upload_datafile"] and self.filename:
            file_size_mb = os.path.getsize(self.filename) / (1024 * 1024)
            if (
                isinstance(self.config["upload_datafile"], bool)
                or file_size_mb <= self.config["upload_datafile"]
            ):
                self.add_attachment(self.filename, "Data file")
            else:
                print(f"File size ({file_size_mb:.2f} MB) exceeds the limit. Not uploading.")

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
        if os.path.isfile(template):
            with open(template, "r") as file:
                template_str = file.read()
        else:
            template_str = template
        jinjatemplate = Template(template_str)
        return jinjatemplate.render(
            base_filename=os.path.basename(self.filename),
            filename=self.filename,
            dcdata=self.merged_system.dcdata,
            query=self.merged_system.query_dict,
        )

    def _determine_userid(self) -> Optional[int]:
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
            print("Exception when calling UsersApi->readUsers: %s\n" % e)
            return None
        names = [user.fullname for user in response]
        orgids = [user.orgid for user in response]
        # Search string
        search_string = self.merged_system.dcdata["creator"]
        if not search_string:
            return None

        # Step 1: try to match orgid
        try:
            return response[orgids.index(search_string.lower())].userid
        except ValueError:
            # orgid does not exist
            pass

        # Step 2: try to find exact substring matches
        substring_matches = [name for name in names if search_string.lower() in name.lower()]

        # Step 3: If no exact substring matches, find the closest match
        if substring_matches:
            most_likely_match = substring_matches[0]  # Assuming the first match is the most likely
        else:
            closest_matches = difflib.get_close_matches(search_string, names, n=1, cutoff=0.6)
            most_likely_match = closest_matches[0] if closest_matches else None
        return response[names.index(most_likely_match)].userid

    def _determine_category(self) -> Optional[int]:
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
        category_name = self.config.get("category", None)
        if not category_name:
            return None
        try:
            response = catApi.read_team_experiments_categories(self._team_id)
        except ApiException as e:
            print(
                "Exception when calling ExperimentsCategoriesApi->readTeamExperimentsCategories: %s\n"
                % e
            )
        # find id for search category
        result_id = next((item.id for item in response if item.title == category_name), None)
        return result_id

    def _determine_status(self, status: str) -> Optional[int]:
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
            print(
                "Exception when calling ExperimentsStatusApi->readTeamExperimentsStatus: %s\n" % e
            )
            return None
        return next((item.id for item in response if item.title == status), None)

    def _determine_resource_category(self) -> Optional[int]:
        """
        Determine resource category id from the name.

        Returns
        -------
        int or None
            The resource category ID if found, None otherwise.
        """
        if not self.api_client:
            return None
        category_name = self.config.get("resource_category", None)
        if not category_name:
            return None

        itemsTypesApi = elabapi_python.ItemsTypesApi(self.api_client)
        try:
            # Read all resources categories that are accessible.
            response = itemsTypesApi.read_items_types()
        except ApiException as e:
            print("Exception when calling ItemsTypesApi->readItemsTypes: %s\n" % e)
        # find id for search category
        return next((item.id for item in response if item.title == category_name), None)

    def _create_resource(self, name: str) -> Optional[int]:
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
            itemsApi.patch_item(item_id, body={"title": name})
            print(f"created ElabFTW resource with name {name}")
        except ApiException as e:
            print("Exception when calling ItemsApi: %s\n" % e)
        if item_id is None:
            raise ValueError("Failed to create resource - itemId is None")
        return item_id

    def _search_resource(self, resource: str) -> Optional[int]:
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
            print("Exception when calling ItemsApi->readItems: %s\n" % e)
            return None
        if item_id := next((item.id for item in response if item.title == resource), None):
            return item_id
        else:
            print(f"Could not identify ElabFTW resource corresponding to the name {resource}")
        return None

    def _parse_tags_from_line(self, line: str) -> Optional[int]:
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
        if not self.config["enable_elab"]:
            return

        title = self._render_template(self.config["title_template"])
        body = self._render_template(self.config["body_template"])

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
            print(f"Exception with post or patch experiment: {e}\n")

    def _handle_existing_title(self, experiments_api, title):
        """Handle title when experiment with the same title already exists."""
        try:
            api_response = experiments_api.read_experiments(q=f"'{title}'")
        except ApiException as e:
            print("Exception when calling ExperimentsApi->readExperiments: %s\n" % e)
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
        print("some error occured during creation of lab book entry.")
        print("see log file for details.")
        print("Here some information to create the labbook entry manually:")
        title = self._render_template(self.config["title_template"])
        body = self._render_template(self.config["body_template"])
        category_name = self.config.get("category", None)
        print(f"Entry title: {title}")
        if category_name:
            print(f"Category: {category_name}")
        print(f"Content (in html): {body}")
        print("---- End Content ----")
        if self._attachments:
            print("Attach files: ")
            for file, comment in self._attachments.items():
                print(f"{file}: {comment}")
        if self._tags:
            print(f"Set tags: {self._tags}")
        if self._resources:
            print(f"Link Resources: {self._resources.keys()}")
        if status:
            print(f"Set experiment status: {status}")

    def reset(self, *args, **kwargs):
        """
        Handle deinitializiation of the measurement.

        Called by matrix when measurement is complete. Creates elabFTW entry if
        measurement was successful.
        """
        # if measurement was not unsuccessful a elab entry is generated
        if "status" not in kwargs or kwargs["status"] != "aborted":
            self.conditional_add_file()
            if self.filename:
                # only create measurement if there is a datafile
                try:
                    self.elab_post_experiment(kwargs.get("status", None))
                except Exception:
                    self._backup_info(kwargs.get("status", None))
            else:
                print("no measurement file exists, not creating entry")
        super().reset(*args, **kwargs)
        # reset internal variables to enable reuse of a class instance
        self._attachments = {}
        self._tags = []
        self._resources = {}


# ============================
# initialize system
system = ElabSystem()
