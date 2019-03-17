import string
import redis
import scipy
import collections
import pyfpgrowth as fpg
import pandas as pd
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import PyPDF2


r = redis.StrictRedis(host='ec2-3-208-118-12.compute-1.amazonaws.com', port=28069, password='pb07233ae908a5a1391478380668e68d52cfa102eb9a867f81c9c5dcdece9289c', db=0, charset="utf-8", decode_responses=True)
# r = redis.StrictRedis(host='localhost', port=6379, db=0, charset="utf-8", decode_responses=True)
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

# Scores are decided by the Rule Power Factor (confidence(A => B) * support(A))
def get_scores(transactions, resume_words):
    num_resumes = len(transactions)
    suggestion_scores = collections.Counter()
    patterns = fpg.find_frequent_patterns(transactions, num_resumes / 1.5)
    rules = fpg.generate_association_rules(patterns, 0.5)
    for antecedent, consequent in rules.items():
        if set(antecedent).issubset(resume_words) and antecedent in patterns:
            suggestion_scores[consequent[0]] += ((patterns[antecedent] * consequent[1]))

    suggestions = set.union(*[set(x) for x in suggestion_scores if suggestion_scores[x] >= 3])
    return {x for x in suggestions if x not in resume_words}


def get_suggestions(resume_file):
    curr_resume = parse_resume(resume_file)
    if not curr_resume:
        return {"ERROR: ": "Resume could not be parsed. This may be due to the font, or compression of the file."}
    transactions = build_transaction_matrix()
    scores = get_scores(transactions, curr_resume)
    return list(scores.keys())

