from selenium import webdriver

driver = webdriver.Chrome()
driver.get('http://vpaavpvm0011.xaas.epfl.ch/examSelect')
driver.maximize_window()
driver.implicitly_wait(10)
print(driver.title)
driver.close()