from selenium import webdriver
from selenium.webdriver.common.keys import Keys

driver = webdriver.Chrome()
driver.get('http://vpaavpvm0011.xaas.epfl.ch/examSelect')
driver.maximize_window()
driver.implicitly_wait(10)
print(driver.title)
driver.close()