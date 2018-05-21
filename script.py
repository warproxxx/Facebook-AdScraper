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

def load_facebook():
    url = "https://facebook.com"
    driver = webdriver.Firefox()
    driver.get(url)
    
    username = input("Enter Facebook Username:")
    pswd = getpass.getpass('Enter Facebook Password:')
    
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
    
    if ("profile.php?id=" in url):
        ret_id = get_id(url)
    else:
        driver.get(url)
        time.sleep(4)

        try:
            elem = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CLASS_NAME, 'hidden_elem')))
        except TimeoutException:
            print("Too much time")

        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")

        userId = ''

        for aVals in soup.find_all('a'):
            try:
                text = aVals['data-hovercard']
                ret_id = get_id(text)
                
                if ("/ajax/hovercard/user.php?id={}".format(ret_id) in text):
                    break
            except:
                pass
            
    return ret_id


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
        res = soup.find("div", {"id": "browse_result_area"})

        links = res.find_all('a')
        
        scroll_till_bottom(driver)
        
        for link in links:
            if ('facebook.com' in link['href']):
                if (link['href'] not in linkList):
                    linkList.append(link['href'])
                
    return linkList


# In[7]:


def perform_scraping(df):
    df['ProfileID'] = ""
    df['PagesLiked'] = ""

    for idx, row in df.iterrows():
        print("Getting UserID for {}".format(row['Profile URL']))
        profileId = get_userid(row['Profile URL'], driver)
        df.at[idx, 'ProfileID'] = profileId
        print("The profile id is: {}".format(profileId))

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

driver = load_facebook()

url = input("Enter the URL you want to scrape from")

commentsDf = get_positive(url, driver)

perform_scraping(commentsDf)

userDf = pd.read_csv('currentlogs.csv')

if ('Unnamed: 0' in userDf):
    userDf = userDf.drop('Unnamed: 0', axis=1)

userDf['PagesLiked'] =  userDf['PagesLiked'].astype(str)
userDf['PagesLiked'] =  userDf['PagesLiked'].apply(to_list)
userDf['PagesLiked'] = userDf['PagesLiked'].apply(to_pagename)

pages, ids = get_pagesusers(userDf, colname='PagesLiked')

def get_combined_df(df, pages, ids, colname='PagesLiked'):
    finalDf = pd.DataFrame()
    
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
    
    doc=pd.ExcelWriter('tests.xlsx',engine='xlsxwriter')
    newDf.to_excel(doc,sheet_name='Sheet1')
    
    return newDf

combinedDf = get_combined_df(userDf, pages, ids)

def get_top_pages(df):
    topN = int(input("How many pages you want to see? "))
    
    print("\n")
    saveDf = df.sum(axis=0).sort_values(ascending=False).head(topN)
    print(saveDf)
    
    saveDf.to_csv('toppages.csv')
    print("\nSaved to toppages.csv")

get_top_pages(combinedDf)