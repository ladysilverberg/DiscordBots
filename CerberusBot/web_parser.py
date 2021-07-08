import re
import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

"""
Responsible for parsing the HTML of Lodestone and FFLogs.

"""
class HTML_Parser():
    lodestone_regex = "^(https:\/\/)(eu|na)\.finalfantasyxiv.com/lodestone/character/([0-9]{6,10})\/$"
    fflogs_regex = "^(https:\/\/)www.fflogs.com/reports/([a-zA-Z0-9]+)/#fight=(last|[0-9]{1,2})"

    def __init__(self, config):
        self.config = config

    # Parses the HTML of a Lodestone URL to get player name and character profile
    def get_lodestone_data(self, lodestone_url):
        # Validate Lodestone URL
        regex_result = re.search(HTML_Parser.lodestone_regex, lodestone_url)
        if (regex_result is None) or (not lodestone_url == regex_result.group()):
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["invalid_lodestone_url"])

        # Get Data from Lodestone
        http_req = requests.get(lodestone_url)
        html = BeautifulSoup(http_req.text, 'html5lib')

        lodestone_bio = html.find("div", class_="character__selfintroduction")
        lodestone_name = html.find("p", class_="frame__chara__name")
        lodestone_world = html.find("p", class_="frame__chara__world")
        if (lodestone_bio is None) or (lodestone_name is None) or (lodestone_world is None):
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["lodestone_parsing_error"])

        # Lodestone World strings are always on the format "[World]\xa0([Data Center])"
        lodestone_world = lodestone_world.text
        if lodestone_world is not None:
            lodestone_world = lodestone_world.split('\xa0')[0]
        else:
            lodestone_world = ""

        return (self.config["error_codes"]["success"], (lodestone_name.contents[0], lodestone_bio.contents[0], lodestone_world))

    # Parses the HTML of an FFLogs URL to get data about damage done and deaths
    def get_log_data(self, fflogs_url, name):
        # Validate FFLogs URL
        regex_result = re.search(HTML_Parser.fflogs_regex, fflogs_url)
        if regex_result is None:
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["invalid_logs_url"])
        fflogs_url = regex_result.group()

        # Run the fight summary page through Selenium to get the HTML contents rendered by JavaScript
        driver = webdriver.Firefox(executable_path=self.config["gecko_driver_path"])
        driver.get(fflogs_url+"&type=summary")
        try:
            ep = EC.presence_of_element_located((By.ID, "summary-damage-done-0"))
            WebDriverWait(driver, 15).until(ep)
        except TimeoutException:
            driver.quit()
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["selenium_timeout"])

        html = BeautifulSoup(driver.page_source, 'html5lib')
        driver.quit()

        # Check if User is part of the logs
        if not self.fflogs_contains_user(html, name):
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["log_user_not_found"] + str(name))

        # Get Boss Name
        boss_name = self.fflogs_get_boss_name(html)
        if boss_name is None:
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["broken_log_parsing"])

        # Get Kill Info and Fight Time
        fight_metadata = self.fflogs_get_kill_info(html)
        if fight_metadata is None:
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["broken_log_parsing"])

        # Get Damage % Done
        dmg_done = self.fflogs_get_percent_done(html, "summary-damage-done-0", name)
        if dmg_done is None:
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["broken_log_parsing"])

        # Get Healing % Done
        heal_done = self.fflogs_get_percent_done(html, "summary-healing-done-0", name)
        if heal_done is None:
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["broken_log_parsing"])

        # Get Deaths
        deaths = self.fflogs_get_deaths(html, name)
        if deaths is None:
            return (self.config["error_codes"]["failure"], self.config["error_messages"]["broken_log_parsing"])

        # Return Parsed Data
        return (self.config["error_codes"]["success"], (boss_name, fight_metadata, dmg_done, heal_done, deaths))

    def fflogs_contains_user(self, html, username):
        try:
            raid_comp_table = html.find("table", {"class": "composition-table"})
            raid_comp_table_entry = raid_comp_table.find(lambda tag: tag.name == "a" and username in tag.text)
            if raid_comp_table_entry is None:
                return False
            return True
        except:
            return False

    def fflogs_get_kill_info(self, html):
        try:
            fight_details_elem = html.find("div", {"id": "filter-fight-details-text"})

            # Is Fight a Wipe?
            wipe_elem = fight_details_elem.find("span", {"class": "wipe"})
            if wipe_elem is not None:
                fight_time = self.fflogs_get_fight_time(wipe_elem)
                if fight_time is None:
                    return None
                return ["Wipe", fight_time]

            # Is Fight a Kill?
            kill_elem = fight_details_elem.find("span", {"class": "kill"})
            if kill_elem is not None:
                fight_time = self.fflogs_get_fight_time(kill_elem)
                if fight_time is None:
                    return None
                return ["Kill", fight_time]

            # No Data Found
            return None
        except:
            return None

    def fflogs_get_fight_time(self, elem):
        try:
            fight_time = elem.find("span", {"class": "fight-duration"})
            fight_time = fight_time.text
            fight_time = fight_time.replace("(", "")
            fight_time = fight_time.replace(")", "")
            time_data = fight_time.split(":")
            # Convert Min:Sec string to integer 
            fight_time = (int(time_data[0]) * 60) + int(time_data[1])
            return fight_time
        except:
            return None

    def fflogs_get_deaths(self, html, username):
        try:
            deaths_table = html.find("table", {"id": "summary-deaths-0"})

            # Compile List of Deaths
            deaths = []
            death_entries = deaths_table.findAll(lambda tag: tag.name == "a" and username in tag.text)
            for death_entry in death_entries:
                death_entry = death_entry.parent

                # Get Death Mechanic
                death_mechanic_parent = death_entry.next_sibling
                death_mechanic = death_mechanic_parent.find("span", id=lambda name: name.startswith("death-ability"))
                if death_mechanic is None:
                    death_mechanic = ""
                else:
                    death_mechanic = death_mechanic.contents[0]
                print(death_mechanic)

                # Get Death Time
                death_time_parent = death_mechanic_parent.next_sibling
                death_time = death_time_parent.contents[0]
                death_time = death_time.replace("\n", "")
                death_time = death_time.replace(" ", "")
                time_data = death_time.split(":")
                death_time = (int(time_data[0]) * 60) + int(time_data[1])
                print(death_time)

                # Add Death to List
                deaths.append((death_time, death_mechanic))
            return deaths
        except:
            return None

    def fflogs_get_percent_done(self, html, table_id, username):
        try:
            table = html.find("table", {"id": table_id})
            table_entry = table.find(lambda tag: tag.name == "a" and username in tag.text)
            if table_entry is None:
                return 0.0
            percent_entry = table_entry.parent.next_sibling
            percent_done = percent_entry.find("div", {"class": "report-amount-percent"}).contents[0]
            percent_done = float(percent_done.replace("%", ""))
            return percent_done
        except:
            return None

    def fflogs_get_boss_name(self, html):
        try:
            boss_element = html.find("div", {"id": "filter-fight-boss-text"})
            boss_name = boss_element.contents[0]
            return boss_name
        except:
            return None
