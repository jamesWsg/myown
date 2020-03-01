import json
import requests
from bs4 import BeautifulSoup
import re
import time

def getTarget_div(url):
    try:
        html = requests.get(url,timeout=10)
    except:
        return None
    try:
        print('BeautifulSoup begin')

        bsObj = BeautifulSoup(html.text, 'html.parser')

        tartget=bsObj.find('a',text='Ubuntu 18.04 LTS (Bionic Beaver)').parent.find_next('div')
        ## debug
        print('BeautifulSoup find ok')
        # the following have err
        #tartget=bsObj.find('a',text=re.compile('Ubuntu 16.04 LTS (Xenial Xerus)').parent.find_next('div')

        
    except AttributeError as e:
        return None
    return tartget

def extract_info_from_div(div):
    deb_latest='could not found deb'

    try:
        tds=div.find('table').findAll('td')
        for td in tds:
            ##only collect amd64 package info
            if td.text.strip() == 'Ubuntu Main amd64':
                deb_latest=td.find_next('td').text
                #deb_info['descrip']=td.find_next('td').find_next('td').text
                break

            else:
                td.text.strip() == 'Ubuntu Universe amd64'
                deb_latest=td.find_next('td').text
                break

    except AttributeError as e:
        return None
    return deb_latest


def get_lastest_deb_version(deb):
    print("prepare get latest verison of deb: {}".format(deb))
    url='https://pkgs.org/download/{}'.format(deb)
    target_div = getTarget_div(url)
    if target_div == None:
        print("target_div could not be found")
    else:
        return  extract_info_from_div(target_div)
        #print(deb)
        #print(result)
    


def get_deb_from_file_and_get_latest(filename):
    
    result=[]
    with open(filename,'r') as f:
        for line in f.readlines():
            deb_name=line.split(' ')[0]
            deb_version=line.split(' ')[1]
            deb_info = {}
            deb_info['deb_name']= deb_name
            deb_info['old_version']=deb_version
            deb_info['latest_version'] = get_lastest_deb_version(deb_name)
            result.append(deb_info)
            #print(result)
    return result            
            

filename='all_deb_noez_manual.txt.manual'
#target_deb = get_deb_from_file(filename)
#deb_list = target_deb.keys()



result = get_deb_from_file_and_get_latest(filename)


print(result)

with open('result.json','w') as f:
    f.write(json.dumps(result))


#pandas.read_json(json.dumps(target_deb)).to_csv('pandas.csv')


