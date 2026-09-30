# Agentic Coding

We provide several ways to interact with a coding agent that allow you
to perform common tasks with its assistance. In the next sections, we
will describe approaches that have proven useful in practice.

## Agents

An agent is a coding assistant that works directly in your file system:
it reads and writes files, runs commands, and iterates until the task is
done. Any recent agent framework works with matr1x, e.g. Claude Code,
OpenCode, or pi.

To use an agent, start it in the directory (workspace) you want it to
work on, e.g. your matr1x installation or the folder containing your
system and control files, and describe the task in plain language.

When started in a matr1x repository, the agent reads the `AGENTS.md`
file in the repository root. It contains the project layout, the coding
conventions, and the commands to build, test, and run the package, so
the agent follows the matr1x conventions without further instruction.
The skills described in the next sections add task-specific procedures
on top of that general knowledge.

Typical tasks you can hand to an agent without any skill:

- "Explain what `system_dummy.py` does and how the devices are
  connected."
- "My measurement fails after 100 points. Check the newest log file in
  the log folder and find the cause."
- "Add a new parameter to my system file."
- "Adapt my control GUI to the current matr1x API."

The agent shows you what it changes. Review the result before you accept
it. Think of it as a skilled assistant, not an unsupervised worker.
Also, be aware that the agent requires permissions to write files and
run commands, at least within the workspace. Please apply the same
precautions you would for any tool with access to your system.

## Skill overview

A skill is a set of instructions that teaches the agent how to perform
a specific task, e.g. installing the package or migrating an
installation to a new release.
While the general knowledge from `AGENTS.md` applies to every request,
a skill is only loaded when the task at hand matches it.
Once a skill is installed, the agent applies it automatically when your
request matches its description.
You can also request a skill explicitly, e.g. "use the
`matr1x-migration` skill to update my installation".

Skills can be installed for a single project or system-wide (per user).
The latter makes them available outside of matr1x repositories as
well, which the `matr1x-install` skill needs: in an empty directory
there is no `AGENTS.md` that could point the agent to the skill.

Note that the `AGENTS.md` file already contains instructions on how to
find and when to use a skill.
If you are unsure whether the agent picked the skill up, check its
internal reasoning, which is often hidden or collapsible in the dialog.

Please refer to the dedicated [skill page](https://andythomas.github.io/matr1x/skills.html)
for installation instructions and a detailed description of each skill.
The sections below explain how to use the individual skills.

## Skill: matr1x-install

This skill installs the complete package into an empty directory:
it sets up the dependencies, clones the repository, creates the
configuration, and performs the desktop integration.
As explained above, it is meant to be installed in the global skill
directory, so that it also works outside of a matr1x repository.
Since that directory may hold skills from other sources as well, the
skill is named `matr1x-install` to stay clearly identifiable.

To use it, change into the target directory and instruct the agent,
e.g. "Please install matr1x as described in the matr1x-install skill."
If anything fails, the agent checks the newest files in `~/logs`
for the underlying cause and attempts to fix the issue on its own.

## Skill: matr1x-migration

As explained in the [deprecation](development/deprecation.md) section,
the API and configuration options change with some releases and have
to be adjusted accordingly.
This skill performs these adjustments automatically for your
configuration, system files, and/or control GUIs.

To use it, change into the directory where your installation is
located and instruct the agent, e.g. "migrate my matr1x installation
from 8.5 to 8.6 using the `matr1x-migration` skill".
Specifying the current and the target version helps the skill, because
it applies the migration steps version by version.

## Skill: matr1x-write-control

This skill guides the agent through writing a control GUI, i.e. a
`control_<name>.py` file with one `GuiDict` panel per instrument, the
SCPI interface for measurement systems, and the `main()` entry point.
It is part of the repository, so it is available in every installation
without further setup.

To use it, start the agent in your installation and instruct it, e.g.
"write a control GUI for my Lake Shore temperature controller using
the `matr1x-write-control` skill".
The agent creates the file, smoke-tests the start-up offscreen, and
finally starts the control for you to try out interactively.

## Skill: matr1x-security

This skill is used by our package maintainers to address security alerts
in our packages.
It reads the security alerts reported by `uv audit` and updates the
affected dependencies accordingly, addressing security vulnerabilities
and outdated dependencies.
