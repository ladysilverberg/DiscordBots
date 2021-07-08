class Policy:
    def __init__(self, config):
        self.config = config

    def check_drs_logs(self, data):
        # Unpack Fight Data
        boss_name = data[0]
        kill_status = data[1][0]
        fight_time = data[1][1]
        dmg_done = data[2]
        heal_done = data[3]
        deaths = data[4]

        score = 0

        # Add Penalty for deaths
        num_deaths = len(deaths)
        score += num_deaths * 10

        # Add Penalty for wipes
        if "Wipe" in kill_status:
            score += 7

        # Easy penalty is damage and healing is good
        score -= dmg_done * 3
        score -= heal_done

        # Add Penalty for failed mechanics
        trinity_names = ["Trinity Avowed Savage", "Trinité Féale Savage"]
        queen_names = ["The Queen Savage", "Garde-La-Reine Savage"]
        if boss_name in trinity_names:
            for death in deaths:
                death_mech = death[1]
                if death_mech == "Heat Shock" or death_mech == "Cold Shock":
                    score += 5
        elif boss_name in queen_names:
            for death in deaths:
                death_mech = death[1]
                if death_mech == "The Means" or death_mech == "Queen's Justice":
                    score += 5
        else:
            return (self.config["error_codes"]["failure"], boss_name + " is not a valid boss for DRS logs. Please provide logs for either Trinity Avowed Savage or The Queen Savage")

        if score <= self.config["accept_threshold"]:
            return (self.config["error_codes"]["success"], True)
        elif score > self.config["reject_threshold"]:
            return (self.config["error_codes"]["success"], False)
        else:
            return (self.config["error_codes"]["manual_check"], "The logs you provided has been flagged for manual review. Once our staff has had a look at it you will recieve a message.")
