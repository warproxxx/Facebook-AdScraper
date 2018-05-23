from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import TimeoutException

import getpass

from bs4 import BeautifulSoup, Comment
import re
import pandas as pd
import os
import numpy as np

from urllib.parse import urlparse, parse_qs
import os.path

import random

import time

import ast

import nltk
from nltk import sentiment, word_tokenize, pos_tag, ne_chunk
from nltk.corpus import opinion_lexicon
from nltk.tokenize import treebank

import matplotlib.pyplot as plt
import seaborn as sns

import psutil

def load_facebook(username, pswd):
    url = "https://facebook.com"
    driver = webdriver.Firefox()
    driver.get(url)
    
    driver.find_element_by_id('email').send_keys(username)
    driver.find_element_by_id('pass').send_keys(pswd)
    driver.find_element_by_id('pass').send_keys(Keys.ENTER)
    
    try:
        elem = WebDriverWait(driver, 2).until(EC.title_contains("Facebook"))
    except TimeoutException:
        print("Too much time")
    
    return driver

def get_nltk_sentiment(sentence, method):
        
    if (method == 'vader'):
        sa = sentiment.vader.SentimentIntensityAnalyzer()
        output = sa.polarity_scores(str(sentence))

        return output['compound']
    
    elif (method == 'liu'):
        
        wordType = ''
        
        if "PERSON" in str(ne_chunk(pos_tag(word_tokenize(sentence)))):
            wordType = 'tag'
        
        tokenizer = treebank.TreebankWordTokenizer()
        pos_words = 0
        neg_words = 0
        tokenized_sent = [word.lower() for word in tokenizer.tokenize(sentence)]
        
        for word in tokenized_sent:
            if word in opinion_lexicon.positive():
                pos_words += 1
            elif word in opinion_lexicon.negative():
                neg_words += 1
                
        if pos_words > neg_words:
            return 'Positive'
        elif pos_words < neg_words:
            return 'Negative'
        elif pos_words == neg_words:
            if wordType == 'tag':
                return 'Positive'
            else:
                return 'Neutral'

def get_comments(url, driver):
    
    pagePath = urlparse(url).path
    pName = pagePath.split("/")[1]
    
    driver.get(url)
    
    try:
        elem = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CLASS_NAME, "fbPhotoSnowliftContainer")))
    except TimeoutException:
        print("Too much time")
    
    while True:
        time.sleep(2)
        
        try:
            driver.find_elements_by_xpath("(//a[contains(text(),'View more comments')])")[3].click()
            print("Viewing more comments")
        except:
            break
            
    html = driver.page_source

    soup = BeautifulSoup(html, "lxml")

    comments = soup.find_all("div", class_="UFICommentContent")

    df = pd.DataFrame(columns=['Comment', 'Profile URL'])

    for comment in comments:
        body = comment.find("span", class_="UFICommentBody").getText()
        currURL = comment.find('a', href=True)['href']
        
        if (currURL.find(pName) == -1):   
            df = df.append({'Comment': body, 'Profile URL': currURL}, ignore_index=True)
            

    return df

def get_positive(url, driver):
    df = get_comments(url, driver)
    df['Sentiment'] = df['Comment'].apply(get_nltk_sentiment, method="liu")
    newDf = df[df['Sentiment'] == 'Positive'].drop_duplicates('Profile URL', keep='first')
    
    newDf = newDf.reset_index(drop=True)
    return newDf

def get_id(text):
    parsed = urlparse(text)
    parsed_dict = parse_qs(parsed.query)
    userId = parsed_dict['id']

    return userId[0]

def get_userid(url, driver):
    ret_id = ''
    ret_name = ''
    ret_city = ''
    
    driver.get(url)
    time.sleep(4)

    try:
        elem = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CLASS_NAME, 'hidden_elem')))
    except TimeoutException:
        print("Too much time")
        
        
    html = driver.page_source
    soup = BeautifulSoup(html, "lxml")
    
    if ("profile.php?id=" in url):
        ret_id = get_id(url)
    else:
        userId = ''

        for aVals in soup.find_all('a'):
            try:
                text = aVals['data-hovercard']
                ret_id = get_id(text)
                
                if ("/ajax/hovercard/user.php?id={}".format(ret_id) in text):
                    break
            except:
                pass
            
    spans = soup.find_all('span')

    for span in spans:
        if (span.has_attr('data-testid')):
            ret_name = span.get_text()

    divs = soup.find_all('div', {'id': 'intro_container_id'})

    for div in divs:
        if('Lives in' in div.get_text()):
            aCollection = div.find_all('a', {"class": "profileLink"})

            for a in aCollection:
                if('hometown' in a['href']):
                    ret_city = a.get_text()
            
    return ret_id, ret_name, ret_city


# In[6]:


def scroll_till_bottom(driver):
    count = 0
    
    SCROLL_PAUSE_TIME = 0.7

    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);") # Scroll down to bottom
        time.sleep(SCROLL_PAUSE_TIME) # Wait to load page

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            count = count + 1
            
            if (count > 5):
                print('Probably reached end of result trying again')
                break
        else:
            print("Loading new results")
            count = 0
            
        last_height = new_height #while Loading more results... exists
        
def scrape_likes(user,driver):
    url = 'https://www.facebook.com/search/{}/pages-liked/'.format(user)
    driver.get(url)
    
    linkList = []
    
    try:
        elem = WebDriverWait(driver, 2).until(EC.title_contains("Pages liked by"))
    except TimeoutException:
        print("Too much time")
    
    time.sleep(3)
    
    scroll_till_bottom(driver)

    html = driver.page_source
    soup = BeautifulSoup(html, "lxml")

    if "We couldn\'t find anything for" in str(soup):
        print("No likes found for {}".format(user))
    else:
        try:
            res = soup.find("div", {"id": "browse_result_area"})

            links = res.find_all('a')
            
            scroll_till_bottom(driver)
            
            for link in links:
                if ('facebook.com' in link['href']):
                    if (link['href'] not in linkList):
                        linkList.append(link['href'])
        except:
            pass
                
    return linkList


# In[7]:


def perform_scraping(df):
    df['ProfileID'] = ""
    df['ProfileName'] = ""
    df['ProfileCity'] = ""
    df['PagesLiked'] = ""
    
    count = 0

    for idx, row in df.iterrows():
        print("{} of {}".format(count+1, df.shape[0]))
        print("Getting UserID for {}".format(row['Profile URL']))
        profileId, profileName, profileCity = get_userid(row['Profile URL'], driver)
        
        df.at[idx, 'ProfileID'] = profileId
        df.at[idx, 'ProfileName'] = profileName
        df.at[idx, 'ProfileCity'] = profileCity
        
        print("The profile id is: {}".format(profileId))
        print("The profile name is: {}".format(profileName))
        print("The current city is: {}\n".format(profileCity))

        sleepsecs = random.randint(2,6)
        print("Sleeping for {} seconds".format(sleepsecs))
        time.sleep(sleepsecs)

        print("Getting pages liked by {}".format(profileId))
        pagesLiked = scrape_likes(profileId, driver)
        df.at[idx, 'PagesLiked'] = pagesLiked
        print("The pages liked are {}".format(pagesLiked))

        sleepsecs = random.randint(2,6)
        print("Sleeping for {} seconds".format(sleepsecs))
        time.sleep(sleepsecs)

        print('\n')

        df.to_csv('currentlogs.csv', index=False)
        count += 1


# In[8]:


def to_list(liststr):
    try:
        pageList = ast.literal_eval(liststr)
        return pageList
    except:
        return []


# In[9]:


def to_pagename(pageList):
    cleanURLs = []
        
    for page in pageList:
        if ("places/intersect" in page):
            continue #as that is a repeat

        try:
            url = page[:page.find('?')]
        except:
            url = page
            
        url = url.strip("/").replace("https://www.facebook.com/", "")
        
        cleanURLs.append(url)

    return cleanURLs


# In[10]:


def get_pagesusers(df, colname):
    allPages = []

    for idx, row in df.iterrows():
        for page in row[colname]:
            allPages.append(page)

    uniquePages = list(set(allPages))

    userIds = []

    for idx, row in df.iterrows():
        try:
            row['ProfileID'] = int(row['ProfileID'])
        except:
            row['ProfileID'] = row['ProfileID']

        userIds.append(row['ProfileID'])
    
    return uniquePages, userIds
    
username = input("Enter Facebook Username:")
pswd = getpass.getpass('Enter Facebook Password:')

for process in psutil.process_iter():
    if 'firefox' in process.name():
        print("Killed a firefox instance")
        process.kill()

def get_combined_df(df, pages, ids, filename, colname='PagesLiked'):
    finalDf = pd.DataFrame()
    
    sheet2Df = df[['ProfileID', 'ProfileName', 'ProfileCity']]

    df = df.set_index('ProfileID')

    multiDf = df[colname].apply(pd.Series).stack()

    finalDf['ProfileID'] = multiDf.reset_index()['ProfileID']
    finalDf['Page'] = multiDf.reset_index()[0]



    newDf = pd.DataFrame(columns=pages)

    newDf['ProfileID'] = list(set(finalDf['ProfileID']))
    newDf = newDf.set_index('ProfileID')

    for idx, row in newDf.iterrows():
        newDf.loc[idx] = 0
        likedPages = finalDf[finalDf['ProfileID'] == idx]['Page']
        newDf.loc[idx][likedPages] = 1

    print("Generating Heatmap")
    doc=pd.ExcelWriter('heatmap-{}.xlsx'.format(filename) ,engine='xlsxwriter')
    newDf.to_excel(doc,sheet_name='Sheet1')
    sheet2Df.to_excel(doc, sheet_name='Sheet2')
    
    print("Heatmap saved to heatmap-{}.xlsx".format(filename))

    return newDf

def get_top_pages(df, results, filename):
    saveDf = df.sum(axis=0).sort_values(ascending=False).head(results)
    print(saveDf)
    
    saveDf.to_csv('toppages-{}.csv'.format(filename))
    print("\nSaved to toppages-{}.csv".format(filename))
    
driver = load_facebook(username, pswd)

urls = []
uniquenames = []

results = int(input("Enter the number of results you want to save: (50 recommended at least): "))
print("\n")

url = input("Enter the URL you want to scrape from (Type E after completion): ")
name = input("Enter a unique name to represent this while saving the file (Type E after completion): ")

urls.append(url)
uniquenames.append(name)



while url != "E":
    url = input("Enter the URL you want to scrape from (Type E after completion): ")
    name = input("Enter a unique name to represent this while saving the file (Type E after completion): ")

    urls.append(url)
    uniquenames.append(name)
    
    
count = 0

for url in urls:

    print("About to extract comments from {}".format(url))

    commentsDf = get_positive(url, driver)

    perform_scraping(commentsDf)

    userDf = pd.read_csv('currentlogs.csv')

    if ('Unnamed: 0' in userDf):
        userDf = userDf.drop('Unnamed: 0', axis=1)

    userDf['PagesLiked'] =  userDf['PagesLiked'].astype(str)
    userDf['PagesLiked'] =  userDf['PagesLiked'].apply(to_list)
    userDf['PagesLiked'] = userDf['PagesLiked'].apply(to_pagename)

    pages, ids = get_pagesusers(userDf, colname='PagesLiked')

    combinedDf = get_combined_df(userDf, pages, ids, uniquenames[count])

    get_top_pages(combinedDf, results, uniquenames[count])
    
    count += 1