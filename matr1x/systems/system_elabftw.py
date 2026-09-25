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
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal, cast

import elabapi_python
from elabapi_python.rest import ApiException
from jinja2 import Template
from pydantic import Field, field_validator
from urllib3.exceptions import HTTPError

from matr1x.core.models import Message, SystemConfigModel
from matr1x.core.system import MergedSystem, System

logger = logging.getLogger(__name__)


class ElabConfig(SystemConfigModel):
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
    parse_hashtags: bool = Field(
        default=True,
        description="Parse #hashtags from description metadata as experiment tags",
    )
    category: str = Field("", description="Category for experiments")
    resource_category: str = Field("", description="Category for resources")
    write_groups: list[str] = Field(
        default_factory=list,
        description="Team group names to grant write access on created items and experiments",
    )

    @field_validator("write_groups", mode="before")
    @classmethod
    def coerce_write_groups(cls, value: Any) -> Any:
        """Normalize scalar and comma-separated group values from configuration UIs."""
        if value is None:
            return []
        if isinstance(value, str):
            value = value.strip()
            if not value or value == "[]":
                return []
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

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


def _match_group_id(name: str, group_map: dict[str, int]) -> int:
    """Match a group name exactly or by an unambiguous case-insensitive name."""
    name_clean = name.strip()
    if name_clean in group_map:
        return group_map[name_clean]

    matches = [
        group_id for key, group_id in group_map.items() if key.casefold() == name_clean.casefold()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Configured eLabFTW write group '{name_clean}' is ambiguous")

    available = sorted(group_map.keys())
    raise ValueError(
        f"Configured eLabFTW write group '{name_clean}' was not found. "
        f"Available team groups: {available}"
    )


def _parse_permissions(value: str | None) -> dict[str, object]:
    """Parse an eLabFTW permission field without discarding existing grants."""
    if value is None or not value.strip():
        return {"teams": [], "users": [], "teamgroups": []}
    try:
        permissions = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("Invalid eLabFTW permission JSON") from error
    if not isinstance(permissions, dict):
        raise ValueError("eLabFTW permissions must be a JSON object")
    return permissions


def _merge_teamgroup_ids(field_val: str | None, group_ids: list[int]) -> tuple[bool, str]:
    """Merge group IDs into the teamgroups list of a permission field."""
    perm_dict = _parse_permissions(field_val)
    raw_teamgroups = perm_dict.setdefault("teamgroups", [])
    if not isinstance(raw_teamgroups, list):
        raise ValueError("eLabFTW permission 'teamgroups' must be a list")
    current_teamgroups = cast(list[object], raw_teamgroups)

    if not all(isinstance(group_id, int) for group_id in current_teamgroups):
        raise ValueError("eLabFTW permission team group IDs must be integers")
    existing_set = {group_id for group_id in current_teamgroups if isinstance(group_id, int)}
    changed = False
    for gid in group_ids:
        if gid not in existing_set:
            current_teamgroups.append(gid)
            existing_set.add(gid)
            changed = True

    return changed, json.dumps(perm_dict)


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
        self._created_resources: dict[str, int] = {}
        self._resolved_write_group_ids: list[int] = []
        self._resolved_user: dict[str, Any] | None = None

    def _init_api_client(self) -> None:
        """Create and verify ApiClient connection against the server."""
        if not getattr(self.sensitive_config, "host", None) or not getattr(
            self.sensitive_config, "api_key", None
        ):
            self.report(
                Message(
                    "ElabFTW connection host or API key not found in the TOML config, make "
                    "sure host address and API key of the server are specified.",
                    to_comment=False,
                )
            )
            raise ValueError(
                "ElabFTW host or API key not found in the TOML config, make sure "
                "host address and API key of the server are specified."
            )

        configuration = elabapi_python.Configuration()
        configuration.api_key["api_key"] = self.sensitive_config.api_key
        configuration.api_key_prefix["api_key"] = "Authorization"
        configuration.host = self.sensitive_config.host + "/api/v2"
        configuration.debug = self.config.debug
        configuration.verify_ssl = True

        self.api_client = elabapi_python.ApiClient(configuration)
        self.api_client.set_default_header(
            header_name="Authorization", header_value=self.sensitive_config.api_key
        )

        try:
            info_client = elabapi_python.InfoApi(self.api_client)
            info_client.get_info()
        except Exception as error:
            self._handle_connection_error(error)

    def _link_or_create_sample_resources(self) -> None:
        """Add resource links for sample names found in metadata, creating if requested."""
        for key in ["identifier", "relation"]:
            samplename = self.merged_system.dcdata[key]
            if not samplename:
                continue
            try:
                self.add_resource(samplename)
            except Exception:
                logger.debug(
                    "Could not look up ElabFTW resource %s; attempting creation",
                    samplename,
                    exc_info=True,
                )
            if self.config.create_resource and samplename not in self._resources:
                resource_id = self._create_resource(samplename)
                if resource_id is not None:
                    self._resources[samplename] = resource_id
                    self._created_resources[samplename] = resource_id

        identifier = self.merged_system.dcdata.get("identifier")
        relation = self.merged_system.dcdata.get("relation")
        if identifier in self._created_resources and relation in self._resources:
            identifier_id = self._created_resources[identifier]
            relation_id = self._resources[relation]
            if identifier_id != relation_id:
                elabapi_python.LinksToItemsApi(self.api_client).post_entity_items_links(
                    "items", identifier_id, relation_id
                )

    def set(self, *args, **kwargs):
        """
        Initialize the server connection and resource and create if requested.

        The resource will be linked to the experiment entry generated
        during reset.
        """
        super().set(*args, **kwargs)
        if not self.config.enable_elab:
            return

        self._init_api_client()
        if self.api_client is None:
            return

        self._validate_elab_configuration()
        self._link_or_create_sample_resources()

    def _handle_connection_error(self, error: Exception) -> None:
        """Allow offline fallback only for connection or temporary errors."""
        if isinstance(error, ApiException):
            unavailable = error.status in (0, 408, 429) or (
                error.status is not None and error.status >= 500
            )
        else:
            unavailable = isinstance(error, (HTTPError, OSError))
        if not unavailable:
            raise ValueError(
                f"ElabFTW connection configuration or access was rejected: {error}"
            ) from error
        if self.config.require_server:
            self.report(
                Message(
                    "ElabFTW connection could not be established "
                    "but is configured to be required.",
                    to_comment=False,
                )
            )
            raise ConnectionError("ElabFTW connection could not be established") from error
        self.report(
            Message(
                "ElabFTW connection could not be established\n"
                "no labbook entry will be created, but we continue.",
                to_comment=False,
            )
        )
        self.api_client = None

    def _resolve_team_groups(self) -> list[int]:
        """Fetch team groups from eLabFTW and resolve configured write_groups to IDs."""
        if not self.config.write_groups or not self.api_client:
            return []
        if not self._team_id:
            raise ValueError("ElabFTW teamid is required when write_groups are configured")

        payload = self.api_client.call_api(
            f"/teams/{self._team_id}/teamgroups",
            "GET",
            header_params={"Accept": "application/json"},
            response_type=object,
            _return_http_data_only=True,
        )
        groups = payload.values() if isinstance(payload, dict) else payload
        group_map = {
            str(group["name"]).strip(): int(group["id"])
            for group in groups
            if isinstance(group, dict) and group.get("id") is not None and group.get("name")
        }
        resolved_ids = [_match_group_id(name, group_map) for name in self.config.write_groups]

        return list(dict.fromkeys(resolved_ids))

    def _validate_elab_configuration(self) -> None:
        """Validate connected configuration and resolve team groups before setup proceeds."""
        self._resolved_write_group_ids = self._resolve_team_groups()

    def _fetch_entity_permissions(
        self, entity_type: Literal["items", "experiments"], entity_id: int
    ) -> tuple[str | None, str | None]:
        """Fetch entity canwrite and canread permissions."""
        if not self.api_client:
            return None, None
        if entity_type == "items":
            entity = elabapi_python.ItemsApi(self.api_client).get_item(entity_id)
        elif entity_type == "experiments":
            entity = elabapi_python.ExperimentsApi(self.api_client).get_experiment(entity_id)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

        return entity.canwrite, entity.canread

    def _patch_entity_permissions(
        self,
        entity_type: Literal["items", "experiments"],
        entity_id: int,
        patch_body: dict[str, str],
    ) -> None:
        """Send PATCH request with updated permissions."""
        if not patch_body or not self.api_client:
            return
        if entity_type == "items":
            elabapi_python.ItemsApi(self.api_client).patch_item(id=entity_id, body=patch_body)
        elif entity_type == "experiments":
            elabapi_python.ExperimentsApi(self.api_client).patch_experiment(
                id=entity_id, body=patch_body
            )

    def _grant_group_permissions(
        self, entity_type: Literal["items", "experiments"], entity_id: int
    ) -> None:
        """Grant configured groups read and write permissions on an entity."""
        if not self._resolved_write_group_ids or not self.api_client:
            return

        try:
            canwrite_val, canread_val = self._fetch_entity_permissions(entity_type, entity_id)
        except ApiException as e:
            self.report(
                Message(
                    f"Exception fetching {entity_type} {entity_id} to update permissions: {e}\n",
                    to_comment=False,
                )
            )
            raise ValueError(f"Failed to fetch {entity_type} {entity_id} permissions: {e}") from e

        patch_body: dict[str, str] = {}
        changed_w, new_canwrite = _merge_teamgroup_ids(
            canwrite_val, self._resolved_write_group_ids
        )
        if changed_w:
            patch_body["canwrite"] = new_canwrite

        changed_r, new_canread = _merge_teamgroup_ids(canread_val, self._resolved_write_group_ids)
        if changed_r:
            patch_body["canread"] = new_canread

        try:
            self._patch_entity_permissions(entity_type, entity_id, patch_body)
        except ApiException as e:
            self.report(
                Message(
                    f"Exception patching permissions for {entity_type} {entity_id}: {e}\n",
                    to_comment=False,
                )
            )
            raise ValueError(
                f"Failed to update permissions on {entity_type} {entity_id}: {e}"
            ) from e

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
        self._resolved_user = None
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
            self._resolved_user = response[idx]
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
            self._resolved_user = response[names.index(most_likely_match)]
            return self._resolved_user["userid"]

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

        try:
            payload = self.api_client.call_api(
                "/teams/current/resources_categories",
                "GET",
                header_params={"Accept": "application/json"},
                response_type=object,
                _return_http_data_only=True,
            )
        except ApiException as e:
            self.report(
                Message(
                    f"Exception when calling /teams/current/resources_categories: {e}\n",
                    to_comment=False,
                )
            )
            return None
        except Exception as e:  # noqa: BLE001  # report any api error
            self.report(
                Message(
                    f"Exception when calling /teams/current/resources_categories: {e}\n",
                    to_comment=False,
                )
            )
            return None

        for item in payload:
            title = item["title"]
            category_id = item["id"]
            if title == category_name and category_id is not None:
                return int(category_id)
        return None

    def _create_resource(self, name: str, tags: list[str] | None = None) -> int | None:
        """
        Create a new resource in elabFTW.

        This method creates a new resource with the given name and the category
        specified in the configuration, and assigns configured group permissions.

        Parameters
        ----------
        name
            The name of the resource to be created.
        tags
            Optional tags to assign to the resource.

        Returns
        -------
        int or None
            The ID of the newly created resource.

        Raises
        ------
        ValueError
            If a valid resource category could not be found or creation fails.
        """
        if not self.api_client:
            return None
        resource_cat = self._determine_resource_category()
        if not resource_cat:
            raise ValueError("Valid resource category could not be found, but is needed.")
        itemsApi = elabapi_python.ItemsApi(self.api_client)
        try:
            create_body = {"category": resource_cat}
            if tags:
                create_body["tags"] = tags
            response = itemsApi.post_item_with_http_info(body=create_body)
            headers = response[2]
            location = headers.get("Location") or headers.get("location")
            if location is None:
                raise ValueError("Missing Location header in create item response")
            item_id = int(location.split("/").pop())
            # Category and tags are assigned by the creation request. Sending
            # them again in the generic entity PATCH is rejected by some
            # eLabFTW versions as an invalid update target.
            itemsApi.patch_item(body={"title": name}, id=item_id)
            if self._resolved_write_group_ids:
                self._grant_group_permissions("items", item_id)
        except ApiException as e:
            self.report(Message(f"Exception when calling ItemsApi: {e}\n", to_comment=False))
            raise ValueError("Failed to create resource due to eLabFTW API error") from e
        self.report(Message(f"created ElabFTW resource with name {name}", to_comment=False))
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
            self.report(
                Message(
                    f"Exception when calling ItemsApi->readItems: {e}\n",
                    to_comment=False,
                )
            )
            return None
        if item_id := next((item.id for item in response if item.title == resource), None):
            return item_id
        else:
            self.report(
                Message(
                    f"Could not identify ElabFTW resource corresponding to the name {resource}",
                    to_comment=False,
                )
            )
        return None

    def _parse_tags_from_text(self, text: str) -> list | None:
        """
        Parse tags from text, tags are marked with #.

        Parameters
        ----------
        text
            Text from which to parse the tags.

        Returns
        -------
        list or None
            Returns a list with parsed tags, otherwise None
        """
        if not text:
            return
        if "#" not in text:
            return
        pattern = r"#(?:\(([^)]+)\)|(\S+))"
        matches = re.findall(pattern, text)

        # Extract matched hashtags
        hashtags = [match[0] if match[0] else match[1] for match in matches]
        return hashtags

    def _prepare_experiment_tags(self) -> None:
        """Allow specialized systems to process the final experiment tags."""

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

        if self.config.parse_hashtags and self.merged_system.dcdata.get("description"):
            additional_tags = self._parse_tags_from_text(self.merged_system.dcdata["description"])
            for tag in additional_tags or []:
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

        self._prepare_experiment_tags()

        catid = self._determine_category()
        if catid:
            params["category"] = catid

        status_id = self._determine_status(status)
        if status_id is not None:
            params["status"] = status_id

        try:
            create_body = {"tags": self._tags}
            _response_body, _status_code, response_headers = (
                experiments_api.post_experiment_with_http_info(body=create_body)
            )

            location = response_headers.get("Location") or response_headers.get("location")
            if location is None:
                raise ValueError("Missing Location header in create experiment response")
            experiment_id = int(location.split("/")[-1])

            if self._resolved_write_group_ids:
                self._grant_group_permissions("experiments", experiment_id)

            experiments_api.patch_experiment(id=experiment_id, body=params)

            self._upload_attachments(str(experiment_id))
            self._link_resources(str(experiment_id))
            if reset_tags:
                self._tags = []

        except ApiException as e:
            self.report(Message(f"Exception with post or patch experiment: {e}\n"))
            raise

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
        logger.error("Detailed error message:")
        backup_info = (
            "some error occured during creation of lab book entry.\n"
            "see log file for details.\n"
            "Here some information to create the labbook entry manually:"
        )
        self.report(Message(backup_info))
        title = self._render_template(self.config.title_template)
        body = self._render_template(self.config.body_template)
        category_name = getattr(self.config, "category", None)
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
        try:
            # Only publish completed measurements with a data file.
            if kwargs.get("status") != "aborted":
                self.conditional_add_file()
                if self.filename:
                    self.elab_post_experiment(kwargs.get("status", ""))
                else:
                    self.report(Message("no measurement file exists, not creating entry"))
        except Exception as error:
            logger.exception("ElabFTW publication failed")
            self.report(Message(f"ElabFTW publication failed: {error}", to_comment=False))
            self._backup_info(kwargs.get("status", ""))
        finally:
            try:
                super().reset(*args, **kwargs)
            finally:
                self._attachments = {}
                self._tags = []
                self._resources = {}
                self._created_resources = {}
                self._resolved_user = None
