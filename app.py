from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from time import sleep
from decouple import config
from datetime import datetime
from pandas import read_csv, to_datetime
import os
from influxdb_client import InfluxDBClient
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from numpy import zeros

USER = os.getenv('TTSEVEN_USER')
PASSWORD = os.getenv('TTSEVEN_PASS')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG')
INFLUXDB_URL = os.getenv('INFLUXDB_URL')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET')
EXECUTION_TIMER = 12 if (os.getenv('EXECUTION_TIMER') == '' or os.getenv('EXECUTION_TIMER') == None) else float(os.getenv('EXECUTION_TIMER'))

def getTransactions(savePath: str = "/raw-statements") -> dict:

     # Set up headless chrome env...
     print("Starting up WebDriver")
     chrome_options = Options()
     chrome_options.add_argument("--headless=new") # for Chrome >= 109
     chrome_options.add_argument("--disable-extensions") #disabling extensions
     chrome_options.add_argument("--disable-gpu") #applicable to windows os only
     chrome_options.add_argument("--disable-dev-shm-usage") #overcome limited resource problems
     chrome_options.add_argument("--no-sandbox") # Bypass OS security model
     prefs = {"download.default_directory" : savePath}
     chrome_options.add_experimental_option("prefs", prefs)
     driver = webdriver.Chrome(options=chrome_options)
     url = "https://app.22seven.com/login"

     success = False
     msg = ""
     accDict = {}

     try: 
          # navigate to page
          print(f"Navigating to '{url}'")
          driver.get(url)

          # # Log into 22Seven...
          print(f"Logging in...")
          driver.find_element(By.XPATH, "/html/body/div/div/div[2]/div/div/div[3]/form/div[1]/div/input").send_keys(USER)
          driver.find_element(By.XPATH, "/html/body/div/div/div[2]/div/div/div[3]/form/div[2]/div[1]/div/input").send_keys(PASSWORD)
          driver.find_element(By.XPATH, "/html/body/div/div/div[2]/div/div/div[3]/form/div[4]/button").click()
          sleep(5)

          # Navigate to 22Seven Transaction page
          url = "https://app.22seven.com/transactions?tab=all"
          print(f"Navigating to '{url}'")
          driver.get(url)
          # sleep(5)

          # download transactions
          print(f"Downloading Transactions")
          downloadCSV = WebDriverWait(driver, 10).until(
               EC.element_to_be_clickable((By.XPATH, "/html/body/div/div/div[2]/div[2]/header/div/div[3]/div/button"))
          )
          # ownloadCSV = .find_element((By.XPATH, "/html/body/div/div/div[2]/div[2]/header/div/div[3]/div/button"))
          downloadCSV.click()
          sleep(5)
          # driver.quit()
          # exit()

          # get current account balances... 
          url = "https://app.22seven.com/accounts"
          print(f"Navigating to '{url}'")
          driver.get(url)
          sleep(10)

          accEl =  WebDriverWait(driver, 10).until(
               EC.element_to_be_clickable((By.XPATH, '/html/body/div/div/div[2]/div[2]/div/div/div[3]/div'))
          )

          accounts = accEl.find_elements(By.XPATH, '*')
          for i, account in enumerate(accounts):
               accName = driver.find_element(By.XPATH, f'/html/body/div/div/div[2]/div[2]/div/div/div[3]/div/div[{i+1}]/div/div[2]/div[1]').get_attribute("textContent")
               accValstr = driver.find_element(By.XPATH, f'/html/body/div/div/div[2]/div[2]/div/div/div[3]/div/div[{i+1}]/div/div[2]/div[2]').get_attribute("textContent")
               
               accVal = -float(accValstr.replace("-", "").replace(",", "")) if "-" in accValstr else float(accValstr.replace(",", ""))
               accDict[accName] = accVal

          success = True
          msg = "transactions downloaded"

     except Exception as e: 
          msg = e
          driver.quit()

     driver.quit()

     retval = {}
     retval["balances"] = accDict
     retval["success"] = success
     retval["msg"] = msg
     
     return retval


def processTransactions(downloadFile: str, accDict: dict ):
     # print(accDic)

     files = os.listdir(downloadFile)
     paths = [os.path.join(downloadFile, basename) for basename in files]
     downloadFile =  max(paths, key=os.path.getctime)

     DFTrans = read_csv(downloadFile, skiprows=[0, 1])
     DFTrans["value"] = DFTrans["Amount"]
     # DFTrans["time"] = row (DFTrans["Date"].iterrows()
     DFTrans["time"] = [datetime.strptime(row, "%Y-%m-%d").isoformat() for row in DFTrans["Date"]]

     balList = []
     for i, row in DFTrans.iterrows():
          balDict = {}
          tags = {}
          fields = {}

          accDict[row["Account"]] -= row['value']

          tags["Account"] = row["Account"]
          fields["value"] = accDict[row["Account"]]
          fields["Category"] = row["Category"]
          fields["Spending Group"] = row["Spending Group"]
          fields["Pay Month"] = row["Pay Month"]
          fields["Split Transaction"] = row["Split Transaction"]
          fields["Description"] = row["Description"]


          balDict["time"] = row["time"]
          balDict["tags"] = tags
          balDict["fields"] = fields
          balDict["measurement"] = "balance"

          balList.append(balDict)

     DFTrans = DFTrans.set_index('time')
     DFTrans = DFTrans.drop(["Date", "Amount"], axis = 1)

     with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG).write_api() as write_api:
          print(f"writing {len(DFTrans.index)} transactions...")
          write_api.write(
               bucket=INFLUXDB_BUCKET, 
               org=INFLUXDB_ORG, 
               record=DFTrans, 
               data_frame_measurement_name="transactions", 
               data_frame_tag_columns=['Spending Group','Category','Pay Month','Split Transaction','Notes', 'Account', 'Description']
          )
          print("transactions written!")

          print(f"writing {len(balList)} balance points...")
          write_api.write(
               bucket=INFLUXDB_BUCKET, 
               org=INFLUXDB_ORG, 
               record=balList
          )
          print("balance data written!")

     return DFTrans

def getBudget():
     return NotImplementedError
     
if __name__ == '__main__':

     print("started 22seven influx ingester!")
     print(f"InfluxDB url: {INFLUXDB_URL}")
     print(f"22Seven Username: {USER}")
     
     while True: 
          savePath = "/home/bauglir/Development/finance/raw-statements"
          retval = getTransactions(savePath=savePath)
          accDict= retval["balances"] 
          success = retval["success"] 
          msg = retval["msg"]

          if not success:
               print(msg)
               break

          try: 
               processTransactions(savePath, accDict)

          except Exception as e: 
               
               print(e.with_traceback())
               break

          print(f"Writing again in {EXECUTION_TIMER} hours")
          sleep (EXECUTION_TIMER*3600)
