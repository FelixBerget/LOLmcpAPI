# Tutorial and description

This is the collection of the MCP and the Skill i use in Claude to genrate full match reports and to make them graphically impressive.

## Skill
The txt file is just the text to generate the Skill without getting the skill directly yourself since it is not readable in GitHub.
The skill file is here and should be plug and play just upload it to your Claude skills which is in settings-capabilities on Claude desktop

## MCP
The MCP files aka the python related files are of course server.py which is the MCP, but also the dependency and version controls.
This can be put in its own folder and then connected via the config. This will give access to a skill called "riot" it should be here (C:\Users\"User"\AppData\Roaming\Claude) on windows and (~/Library/Application Support/Claude/claude_desktop_config.json) on mac
You can also edit it by clicking edit config in settings-developer
This is where you add it to mcpServers in the config like this "mcpServers" : {} and in it name and under that again a command and arguments
In my case a uv command that goes to the folder and runs server.py This folder needs all the files here excluding the skills
