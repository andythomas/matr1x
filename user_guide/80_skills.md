# Using Skills

We provide several skills, i.e., predefined ways to interact with a model, that allow you to perform common tasks without writing code.
In the next sections, we will show you how to use these skills.

## Overview and verbose description

There are several ways to install the skills.
Please refer to the dedicated [skill page](https://andythomas.github.io/matr1x/skills.html) for more information and detailed descriptions of each skill.

## Skill: matr1x-install

This skill allows you to install the package in an empty directory.
It is meant to be installed in the global skill directory; therefore, "matr1x-" is prefixed for better organization.
Simply change into the target directory and instruct the model to install the package using the `matr1x-install` skill.

## Skill: matr1x-migration

As explained in the [deprecation](development/deprecation.md) section, the API and configuration options have to be adjusted with some releases.
While the changes are explained in the release notes, you can use this skill to automatically update your configuration, system files, and/or control GUIs.
The skill is meant to be installed in the global skill directory; therefore, "matr1x-" is prefixed for better organization.

After the skill is installed, change into the directory where your installation is located.
Now, instruct the model to utilize the `matr1x-migration` skill.
We recommend assisting the skill by specifying the current version and the target version of matr1x you are using.

## Skill: dependabot

This skill is used by our package maintainers to automatically update the dependencies of our packages.
This addresses security vulnerabilities and outdated dependencies in our packages.
