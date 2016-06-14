import common.analyser
import common.profilestore
import itertools
import math
import logging
import argparse
import editdistance
import pickle
import os

def makeposterior(evidence_given_matched, prior, marginal_likelihood):
    """ Calculates an update to a prior, with some generous error
    handling for potentially terrible input. 
    
    :param float evidence_given_matched: The probability of the evidence given the match, 0:1.
    :param float prior: The prior likelihood of the match, 0:1.
    :param float marginal_likelihood: The marginal likelihood of getting the evidence, 0:1."""
    calc = (evidence_given_matched * prior) / marginal_likelihood
    if calc <= 0:
      return 0.01
    elif calc > 1:
        return 1.0
    else:
        return calc
    

def areEquivalent(profileone,profiletwo,prior=0.5,threshold=0.6):
    """Runs a number of comparison functions on the
    two profiles, and uses the results to adjust a prior
    Rules for comparison functions:
     
    1. They should accept two profiles
    2. They should return a value between 0 and 1 reflecting the confidence
       the function has that the two profiles are of the same person.
    3. Where the requirements for a comparison are not met, they should
        throw an exception. 

    :param Profile profileone: A profile object.
    :param Profile profiletwo: A profile object.  
    :return: Boolean result of comparison based on threshold, prior, and comparison functions on the two profiles."""

    exactNameWeight = sameNames(profileone,profiletwo)

    bestNameWeight = bestNameDiff(profileone,profiletwo)

    timeWeight = timeComparison(profileone,profiletwo)

    avatarWeight = avatarComparison(profileone,profiletwo)

    friendsWeight = friendsComparison(profileone,profiletwo)

    linkWeight = linkAnalysis(profileone,profiletwo)

    stylometricWeight = stylometricComparison(profileone, profiletwo)

    geographyWeight = geographicProfile(profileone,profiletwo)

#    return prior >= threshold
    return [exactNameWeight, bestNameWeight, timeWeight, avatarWeight, friendsWeight, linkWeight, stylometricWeight, geographyWeight]


def sameNames(profileone, profiletwo):
  """ Comparison function.
  Counts the number of exactly-matching names this person has.
  As profile IDs can sometimes be added as names, skip those."""
  namecount = 0
  validone = 0
  validtwo = 0
  for n1 in profileone.names:
    if not n1.isnumeric():
      validone += 1
      for n2 in profiletwo.names:
        if not n2.isnumeric():
          validtwo += 1
          if n1 == n2:
            namecount += 1
  minlen = min([validone, validtwo])
  return namecount/minlen


def bestNameDiff(profileone, profiletwo):
    """ Applies Levenshtein distance between best names of two profiles."""
    n1 = profileone.bestname()
    n2 = profiletwo.bestname()
    if (not n1) or (not n2):
      return 0
    l1 = profileone.name_length
    l2 = profiletwo.name_length
    diff = editdistance.eval(n1,n2)
    return 1-(diff/(l1 if l1 > l2 else l2))

    
def timeComparison(profileone, profiletwo):
    """ We use a version of the method from Atig et al. 
        to compare time activity profiles. """
    highthresh = 0.2
    lowthresh = 0.08
    tactprofile1 = profileone.timeProfile()
    tactprofile2 = profiletwo.timeProfile()
    if not tactprofile1 or not tactprofile2:
        return 0
    likelihood = 0
    for period in tactprofile1:
        if tactprofile1[period] > highthresh and tactprofile2[period] > highthresh:
            #This is an activity peak.
            likelihood += 1/6
        elif tactprofile1[period] < lowthresh and tactprofile2[period] < lowthresh:
            #This is an inactivity period.
            likelihood += 1/6
    else:
        return likelihood

    
def avatarComparison(profileone, profiletwo):
    """ Use an image comparison approach to compare the
        profile images from the two profiles, confidence
        being the degree of similarity. Uses rms similarity
        between actual pixel value, so fairly confusable."""
    import operator
    from functools import reduce
    totaldiff=906 #adjusted based on observation
#    totaldiff=453
    h1 = profileone.getImageHistogram()
    h2 = profiletwo.getImageHistogram()
    if not h1 or not h2:
      return 0
    rms = math.sqrt(reduce(operator.add,  list(map(lambda a,b: (a-b)**2, h1, h2)))/len(h1) )
    if rms > totaldiff:
      logging.warn("Heuristic on avatar comparison error is wrong.")
      return 0
    return 1-(rms/totaldiff)


def stylometricComparison(profileone, profiletwo):
    """ Compare the bodies of text attached to each profile.
        Confidence is degree of linguistic similarity. Method is
        euclidean distance of function word proportions.  """
    sig1 = profileone.getWritingStyle()
    sig2 = profiletwo.getWritingStyle()
    if not sig1 or not sig2 or sum([sig1[w] for w in sig1]) == 0 or sum([sig2[w] for w in sig2]) == 0 :
      return 0
    rms = math.sqrt(sum([(sig1[word] - sig2[word]) ** 2 for word in sig1]))
    bl = math.sqrt(sum([(sig1[word] + sig2[word]) ** 2 for word in sig1]))
    return 1-(rms/bl)

    
def linkAnalysis(profileone, profiletwo):
    """ Compare the links made by the two profiles.
        Matches mean greater confidence of a connection."""
    from urllib.parse import urlparse

    try:
      ls1 = profileone.getLinks()
      ds1 = [urlparse(link).netloc for link in ls1]
      ls2 = profiletwo.getLinks()
      ds2 = [urlparse(link).netloc for link in ls2]
    except Exception as e:
      logging.warn(e)
      return 0
    
    score = 0
    if len(ls1) == 0 or len(ls2) == 0:
        return 0
    unit = 1/len(ls1)
    for link, domain in zip(ls1,ds1):
        if link in ls2:
            score += unit
        elif domain in ds2:
            score += unit/3
    return score


def geographicProfile(profileone, profiletwo):
    """ Compare the location fingerprint for the two
        profiles. Have to define overlap. """
    score = 0
    if len(profileone.location_set) < 2 or len(profiletwo.location_set) < 2:
        return 0
    unit=1/(len(profileone.location_set)*len(profiletwo.location_set))
    for l1, l2 in itertools.product(profileone.location_set, profiletwo.location_set):
        if l1.near(l2):
           score += unit
    return score


def friendsComparison(profileone,profiletwo):
    """ Decide whether a person's friends are the same.
        Computably, this is done via name comparison."""
    fs1 = list(set(profileone.interacted + profileone.followers + profileone.followed_by + profileone.grouped))
    fs2 = list(set(profiletwo.interacted + profiletwo.followers + profiletwo.followed_by + profiletwo.grouped))
    if len(fs1) < 2 or len(fs2) < 2:
      return 0
    friendcount = 0
    for f1, f2 in itertools.product(fs1,fs2):
        bdiff = bestNameDiff(f1,f2) 
        if bdiff > 0.8: 
            friendcount += 1
    friendmax = min([len(fs1), len(fs2)])
    if friendcount > friendmax:
      return 1
    return (friendcount/friendmax)


def resolve(profiles):
    """ Takes a big list of profiles, resolves those it can and
    then returns a list of Person objects consisting of the resolved profiles."""
    matches = []

    estimate = (len(profiles)*(len(profiles)+1))/2
    count = 0
    #For every pair of profiles.
    for pone, ptwo in itertools.combinations(profiles,2):
        count += 1
        logging.info("{} of {}: Comparing '{}' and '{}'".format(count,estimate,pone.uid,ptwo.uid))
        #Skip comparisons between same network profiles.
        if pone.network != 'Google+' or pone.network == ptwo.network:
          continue
        if (not pone.bestname()) or (not ptwo.bestname()):
          continue
        #Compare based on profile content.
#        if areEquivalent(pone,ptwo):
#            r1 = {'network':pone.network,'network_id':pone.uid}
#            r2 = {'network':ptwo.network,'network_id':ptwo.uid}
#            matches.append([r1,r2])
        matches.append(areEquivalent(pone,ptwo) + [pone.rid, ptwo.rid, pone.network, ptwo.network, 1 if ps.is_match(pone.rid,ptwo.rid) else 0])
    return matches


parser = argparse.ArgumentParser(description='Attempt to match profiles based on content')
parser.add_argument('db', help='The database file governing downloads')
args = parser.parse_args()

block_struct = {}
ps = common.profilestore.ProfileStore(args.db)
prefix = args.db[:-7]
print(prefix)
pfdir = prefix+'-profiles/'

good_bids = []

for record in ps.records:
  if os.path.exists(pfdir+record['uid']+'.pickle'):
    profile = pickle.load(open(pfdir+record['uid']+'.pickle','rb'))
    profile.rid = record['uid']
    if record['network'] == 'Google+':
      bid = profile.bestname()
    else:
      bid = record['search_term']
    if ps.is_matched(profile.rid) and bid not in good_bids:
      good_bids.append(bid)
    if bid in block_struct:
      block_struct[bid].append(profile)
    else:
      block_struct[bid] = [profile]

print("Good BIDs: {}".format(good_bids))

wf = open(prefix+'-predictions.csv','w')
for hi in ['exactnames','bestname','timeactivity','avatars','friends','linkactivity','stylometry','geography','origin.id','target.id','origin.network','target.network','outcome']:
  wf.write("{},".format(hi))
wf.write('{}\n'.format('block'))
for bid in good_bids:
  simple = resolve(block_struct[bid])
  for record in simple:
    for sl in record:
        wf.write("{},".format(sl))
    wf.write("{}\n".format(bid.replace(',',' ')))
wf.close()
