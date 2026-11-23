# Package upgrade

The upgrade of the package itself (as described in the next section) should be performed by a more experienced person such as a "System Coder".

## Installing the new Version

We assume that the initial installation procedure was based on the instructions in section [installation](installation.md).
Update the `matr1x-measurements` dependency of your project to the latest version.
For an even newer version, pull the (less stable!) `development` branch using Github Desktop or the git tool of your choice.
However, please be aware of the implications as indicated [here](https://github.com/andythomas/matr1x/discussions/9) or even participate in the discussion.
Please click on your role to get more detailed information.

## Post-installation procedures

After the package itself was upgraded, there might be additional steps to be done.
These steps are explained for the respective roles in the next section.

::: {.panel-tabset}

### GUI User

All applications will inform about any changes or incompatibilities in case these are revevant to the user and suggest possible next steps if required.

### System Coder

Please read the release notes.
The first paragraphs will indicate any changes that need to be addressed in the system or control files.

It is possible and recommended to utilize an agent to apply these changes automatically.
Please install the package skills using the agent framework of your choice.
Now, prompt for example:

```markdown
please use the matr1x-migration skill to update to 8.5.
```

Please adjust the prompt as desired, e.g. `update from 8.3 to 8.4`.
If you have problems installing the skills, please point the agent to

```markdown
https://andythomas.github.io/matr1x/.well-known/agent-skills/matr1x-migration/SKILL.md
```

:::
