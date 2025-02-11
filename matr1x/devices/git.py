# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2006-2025 matr1x developers
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

import pygit2


class gitDevice:
    config_params = {
        "remote": "get_remote_url",
        "branch": "get_branch_name",
        "hash": "get_commit_hash",
        "status": "get_status",
        "diff": "get_diff",
    }

    def __init__(self, repo_path):
        self.repo_path = repo_path
        try:
            self.repo = pygit2.Repository(self.repo_path)
        except Exception as e:
            print(f"Exception occurred: {e}")
            raise e

    def get_commit_hash(self):
        return self.repo.head.target

    def get_diff(self):
        diff = self.repo.diff()  # Get the diff object
        diff_text = ''
        for patch in diff:
            diff_text += f'Diff for {patch.delta.new_file.path}:\n'
            diff_text += patch.text + '\n'
        return diff_text

    def get_remote_url(self):
        remotes = self.repo.remotes
        if remotes:
            return remotes[0].url
        else:
            return None

    def get_branch_name(self):
        return self.repo.head.shorthand

    def get_status(self):
        status = self.repo.status()
        status_output = {
            'staged': [],
            'modified': [],
            'untracked': [],
            'deleted': [],
            'renamed': [],
            'copied': [],
            'typechanged': [],
            'ignored': [],
            'unmodified': []
        }

        for filepath, flags in status.items():
            if flags & pygit2.GIT_STATUS_INDEX_NEW:
                status_output['staged'].append(filepath)
            elif flags & pygit2.GIT_STATUS_INDEX_MODIFIED:
                status_output['staged'].append(filepath)
            elif flags & pygit2.GIT_STATUS_INDEX_DELETED:
                status_output['staged'].append(filepath)
            elif flags & pygit2.GIT_STATUS_WT_MODIFIED:
                status_output['modified'].append(filepath)
            elif flags & pygit2.GIT_STATUS_WT_NEW:
                status_output['untracked'].append(filepath)
            elif flags & pygit2.GIT_STATUS_WT_DELETED:
                status_output['deleted'].append(filepath)
            elif flags & pygit2.GIT_STATUS_INDEX_RENAMED:
                status_output['renamed'].append(filepath)
            elif flags & pygit2.GIT_STATUS_INDEX_COPIED:
                status_output['copied'].append(filepath)
            elif flags & pygit2.GIT_STATUS_TYPECHANGE:
                status_output['typechanged'].append(filepath)
            elif flags & pygit2.GIT_STATUS_IGNORED:
                status_output['ignored'].append(filepath)
            elif flags & pygit2.GIT_STATUS_CURRENT:
                status_output['unmodified'].append(filepath)

        return status_output
