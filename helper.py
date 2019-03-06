import string
import redis
import scipy
import collections
from apyori import apriori
import pandas as pd
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import PyPDF2


r = redis.StrictRedis(host='localhost', port=6379, db=0, charset="utf-8", decode_responses=True)
r.setnx("resume_id", 1)


def parse_resume(file):
    resume = open(file, 'rb')
    reader = PyPDF2.PdfFileReader(resume)

    page = reader.getPage(0).extractText()
    punctuation = string.punctuation.replace("+", "")
    stop_words = set(stopwords.words('english'))

    table = str.maketrans({key: " " for key in punctuation})
    page = set([x.lower() for x in word_tokenize(page.translate(table))])

    words = set([x for x in page - stop_words if (not any(c.isdigit() for c in x) and len(x) > 1)])
    if len(words) < 10:
        return False

    set_resume(words)
    return words


def set_resume(words):
    p = r.pipeline()
    resume_id = r.get("resume_id")
    p.sadd("resume:" + resume_id, *words)
    p.incr("resume_id")
    p.execute()


def build_transaction_matrix():
    resumes = r.keys('resume:*')
    resume_words = []

    for resume in resumes:
        resume_words.append(list(r.smembers(resume)))

    return resume_words


def get_scores(transactions, resume_words):
    associations = list(apriori(transactions, min_support=0.5, min_confidence=0.8))
    suggestion_scores = collections.Counter()
    for association in associations:
        support = association[1]
        for rule in association[2]:
            base_items = rule[0]
            new_item = list(rule[1])[0]
            confidence = rule[2]
            if not resume_words.intersection(base_items):
                continue
            if new_item in resume_words:
                continue
            suggestion_scores[new_item] += confidence * support

    return suggestion_scores


def get_suggestions(resume_file):
    curr_resume = parse_resume(resume_file)
    if not curr_resume:
        return {"ERROR: ": "Resume could not be parsed. This may be due to the font, or compression of the file."}
    transactions = build_transaction_matrix()
    scores = get_scores(transactions, curr_resume)
    return list(scores.keys())

