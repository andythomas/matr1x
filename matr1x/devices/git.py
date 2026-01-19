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
Git repository interface module for the matr1x data acquisition system.

This module provides classes for interacting with Git repositories.
"""

import pygit2


class gitDevice:
    """
    Interface to Git repositories.

    A class that provides methods to interact with a Git repository using
    the pygit2 library.

    Parameters
    ----------
    repo_path : str
        Path to the Git repository.

    Attributes
    ----------
    repo_path : str
        Path to the Git repository.
    repo : pygit2.Repository
        The pygit2 Repository object.
    config_params : dict
        Dictionary mapping parameter names to method names.
    """

    config_params = {
        "remote": "get_remote_url",
        "branch": "get_branch_name",
        "hash": "get_commit_hash",
        "status": "get_status",
        "diff": "get_diff",
    }

    def __init__(self, repo_path):
        """
        Initialize a gitDevice with the specified repository path.

        Parameters
        ----------
        repo_path : str
            Path to the Git repository.

        Raises
        ------
        Exception
            If the repository cannot be opened.
        """
        self.repo_path = repo_path
        try:
            self.repo = pygit2.Repository(self.repo_path)
        except Exception as e:
            print(f"Exception occurred: {e}")
            raise e

    def get_commit_hash(self):
        """
        Get the hash of the current HEAD commit.

        Returns
        -------
        str
            The hash of the current HEAD commit.
        """
        return self.repo.head.target

    def get_diff(self):
        """
        Get a text representation of the current diff.

        Returns
        -------
        str
            A text representation of the changes in the repository.
        """
        diff = self.repo.diff()  # Get the diff object
        diff_text = ""
        for patch in diff:
            diff_text += f"Diff for {patch.delta.new_file.path}:\n"
            if patch.text is not None:
                diff_text += patch.text + "\n"
        return diff_text

    def get_remote_url(self):
        """
        Get the URL of the first remote.

        Returns
        -------
        str or None
            The URL of the first remote, or None if no remotes are configured.
        """
        remotes = self.repo.remotes
        if remotes:
            return remotes[0].url
        else:
            return None

    def get_branch_name(self):
        """
        Get the name of the current branch.

        Returns
        -------
        str
            The name of the current branch.
        """
        return self.repo.head.shorthand

    def get_status(self):
        """
        Get the status of the repository.

        Returns
        -------
        dict
            A dictionary with keys representing different status categories
            (staged, modified, untracked, etc.) and values as lists of file paths.
        """
        status = self.repo.status()
        status_output = {
            "staged": [],
            "modified": [],
            "untracked": [],
            "deleted": [],
            "renamed": [],
            "copied": [],
            "typechanged": [],
            "ignored": [],
            "unmodified": [],
        }

        for filepath, flags in status.items():
            if flags & pygit2.GIT_STATUS_INDEX_NEW:
                status_output["staged"].append(filepath)
            elif flags & pygit2.GIT_STATUS_INDEX_MODIFIED:
                status_output["staged"].append(filepath)
            elif flags & pygit2.GIT_STATUS_INDEX_DELETED:
                status_output["staged"].append(filepath)
            elif flags & pygit2.GIT_STATUS_WT_MODIFIED:
                status_output["modified"].append(filepath)
            elif flags & pygit2.GIT_STATUS_WT_NEW:
                status_output["untracked"].append(filepath)
            elif flags & pygit2.GIT_STATUS_WT_DELETED:
                status_output["deleted"].append(filepath)
            elif flags & pygit2.GIT_STATUS_INDEX_RENAMED:
                status_output["renamed"].append(filepath)
            # Check if the attribute exists before using it
            elif (
                hasattr(pygit2, "GIT_STATUS_INDEX_COPIED")
                and flags & pygit2.GIT_STATUS_INDEX_COPIED
            ):
                status_output["copied"].append(filepath)
            # Check if the attribute exists before usinsg it
            elif hasattr(pygit2, "GIT_STATUS_TYPECHANGE") and flags & pygit2.GIT_STATUS_TYPECHANGE:
                status_output["typechanged"].append(filepath)
            elif flags & pygit2.GIT_STATUS_IGNORED:
                status_output["ignored"].append(filepath)
            elif flags & pygit2.GIT_STATUS_CURRENT:
                status_output["unmodified"].append(filepath)

        return status_output
