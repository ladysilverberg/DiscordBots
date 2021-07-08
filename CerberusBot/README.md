# Cerberus - A FFXIV Log Verification Bot
Cerberus is a bot for FFXIV Discord Servers which needs log verification functionality. It is mainly developed for the Bozjan Underdogs Discord Server for use in Delubrum Reginae Savage runs, but can be extended to work with virtually any content.

### Usage
The bot operates with some simple commands: !verify, !verify [lodestone URL and !role [role] [fflogs URL]. These are used to "link" discord users to their FFXIV users as well as check logs according to a policy in order to give roles.

### Security
Cerberus aims to store as little data as possibly to ensure user privacy. Currently, it only stores the Discord User ID, FFXIV Character Name, a verification flag and a temporary token which are used to maintain integrity. The tokens utilizes SHA3-256 with some additional random data appended on the end, which makes it infeasible to verify your FFXIV identity without having access to edit the lodestone page of that character.
