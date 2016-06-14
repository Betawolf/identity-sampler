import re
import os
import json
import pickle
import datetime

try:
  import common.logger
except ImportError as ie:
  from sys import path
  path.append(os.path.abspath('.'))
  path.append(os.path.abspath('..'))
  import common.logger

import common.imagestore

class Content:
  """ The Content object wraps varied user publications online, 
  including text, images, video and links. Whatever the medium,
  it is potentially annotated with time, location, category and
  opinion modifiers. """

  IMAGE = 1
  VIDEO = 2
  TEXT = 3
  LINKS = 4
  
  def __init__(self,ctype,body,time,location,category,opinions):
    """ Initialise a Content object.

    :param int ctype: One of Content.{IMAGE,VIDEO,TEXT,LINKS}
    :param str body: The actual content (for images and video being filepaths to local caches).
    :param struct_time time: A struct_time timestamp for the publication of this content item, or None.
    :param Location location: A Location object indicating the best geolocation for the publication event.
    :param str category: A categorisation of the content.
    :param dict opinions: A measurement of opinion about the content (dict contents undefined). """
    self.ctype = ctype
    self.body = body
    self.time = time
    self.location = location
    self.category = category
    self.opinions = opinions



class Location:
  """A Location object defines a geographical location.
    Essentially there are two tacks to this. The first
    is to use a lon/lat tuple, which should be passed
    with a 'detailed' flag, the second is to use a
    string address. """
  
  def __init__(self, location, detailed=False):
      """ Create a Location object. 

      :param location: Either a (lon,lat) coordinate pair tuple or a string. 
      :param detailed: If true, it is presumed that the coordinate pair has been provided. """
      self.detailed = detailed
      self.location = location

  def near(self, otherlocation):
      """ See whether a Location is 'near' another Location.
      This only really works if both Location objects are 'detailed' (i.e. coordinates).
      If they are not detailed, an attempt will be made to find one string in the other
      (e.g. 'Manchester' is near 'Manchester, UK'), but of course this is unlikely to work
      in many cases. A geocoding API could be used to auto-resolve non-detailed
      locations to lon/lat pairs. 

      :param Location otherlocation: A Location object to measure against. """
      from math import radians, cos, sin, asin, sqrt
      if not self.location or not otherlocation.location:
          return False
      elif (not self.detailed) and (not otherlocation.detailed) and isinstance(self.location,str) and isinstance(otherlocation.location,str):
          return (self.location in otherlocation.location) or (otherlocation.location in self.location)
      elif self.detailed and otherlocation.detailed :
          #Actual geographic comparison -- haversine.
          # convert decimal degrees to radians 
          lon1, lat1, lon2, lat2 = map(radians, [self.location[0], self.location[1], otherlocation.location[0], otherlocation.location[1]])

          # haversine formula 
          dlon = lon2 - lon1 
          dlat = lat2 - lat1 
          a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
          c = 2 * asin(sqrt(a)) 
          r = 6371 # Radius of earth in kilometers. Use 3956 for miles
          dist = c * r
          return dist < 10 
      else:
        return False



class Profile:
    """ A Profile reflects an image of a person on one particular network.
    Profile objects hold all the information which has been mined about
    a target from a network. """

    def __eq__(self,other):
      return self.uid == other.uid

    def __hash__(self):
      return hash(self.network+str(self.uid))

    def bestname(self):
      """ Return the 'most natural name' in the set of names a Profile
      is hosting. (One with a space, indicating first and last compoents,
      or at least one which is not numeric. Sets Profile.primary_name
      and Profile.name_length. 

      :return: A string, or None. """
      if not self.primary_name:
        best = None
        for name in self.names:
          if name.find(' ') > -1:
            best = name
            break
          elif name.swapcase != name:
            best = name
        self.primary_name = best
        if best:
          self.name_length = len(best)
      return self.primary_name


    def getImageHistogram(self):
      """ Returns and creates a histogram of
      the primary profile image associated with
      this profile. 
    
      :return: A histogram as generated by Image.histogram()."""
      if not self.histogram:
        from PIL import Image
        size = (128,128)
        if len(self.profile_images) > 0:
          imgfile = self.profile_images[0]
          if imgfile:
            try:
              image = Image.open(imgfile)
              image.thumbnail(size, Image.ANTIALIAS)
              self.histogram = image.histogram()
            except Exception as e:
              logging.warn(e)
              return None
      return self.histogram


    def getWritingStyle(self):
      """ Generate a signature for a series of texts,
          being the proportion of normalised function
          words. 

      :return: A dict with function words as keys and the Profile's normalised frequency of them as values."""
      if not self.writing_style:
        texts = [content.body for content in self.content if content.ctype == Content.TEXT]
        
        if len(texts) > 0:
          function_words = ["a", "it", "up", "for", "some", "as", "not", "who", "if", "there", "do", "our", "an", "more", "were", "has", "that", "been", "on", "would", "is", "to", "every", "so", "are", "no", "which", "his", "then", "can", "or", "also", "may", "was", "had", "than", "be", "of", "with", "into", "this", "even", "should", "any", "my", "when", "her", "their", "by", "only", "all", "its", "upon", "from", "such", "at", "now", "will", "in", "things", "down", "shall", "and", "must", "what", "have", "the", "but", "one", "your"]
          sig = {}
          norm = 0
          for text in texts:
              textarr = text.lower().split()
              for word in function_words:
                  #count words in document
                  sig[word] = textarr.count(word)
              #increment total text length
              norm += len(textarr)
          
          #normalise
          for word in sig:
              sig[word] = sig[word]/norm
          self.writing_style = sig
      return self.writing_style

    def timeProfile(self):
        """ Transform a list of times into an
            activity profile, based on the six
            groupings used in Atig et al. 
            
            00.00-3.59, 4.00-7.59, 8.00-11.59,
            12.00-15.59, 16.00-19.59 and 20.00-23.59

        :return: A dict with activity periods (index into above set of ranges) keys and normalised frequency values.
        """
        if not self.tactprofile:
          times = self.activity_timestamps
          if len(times) == 0:
               return None
          tactprofile = {}
          unit = 1/len(times)
          for i in range(0,6,1):
              tactprofile[i] = 0
          for t in times:
              if t.tm_hour < 4:
                  tactprofile[0] += unit
              elif t.tm_hour > 3 and t.tm_hour < 8:
                  tactprofile[1] += unit
              elif t.tm_hour > 7 and t.tm_hour < 12:
                  tactprofile[2] += unit
              elif t.tm_hour > 11 and t.tm_hour < 16:
                  tactprofile[3] += unit
              elif t.tm_hour > 15 and t.tm_hour < 20:
                  tactprofile[4] += unit
              elif t.tm_hour > 19:
                  tactprofile[5] += unit
          self.tactprofile = tactprofile
        return self.tactprofile


    def getLinks(self):
      """ Return all the links from a profile,
      including those which might be in TEXT
      content. """
      if not self.linklist:
        links = []
        lre = re.compile(r"(https?://[^ ]+)")
        for content in self.content:
            if content.ctype == Content.TEXT:
                links += lre.findall(content.body)
            elif content.ctype == Content.LINKS:
                links += [content.body]
        self.linklist = [l for l in links if l]
      return self.linklist


    def __init__(self,id,network,source,dated=None):
      """ Create a Profile object.
      
      :param str id: The ID of the profile (usually from the network).
      :param str network: A string identifying the network of origin.
      :param str source: A string containing the full URL for the profile's source. 
      :param datetime dated: A datetime object indicating when the profile was collected (defaults to `now`). """ 
      self.uid = id
      self.tactprofile = None
      self.histogram = None
      self.writing_style = None
      self.primary_name = None
      self.name_length = 0
      self.linklist = None
      self.network = network
      self.source = source
      if dated == None:
        self.collected_at = datetime.datetime.now()
      else:
        self.collected_at = dated
      #Contact Details
      self.web_links = []        #Free URLs for a personal home page or similar.
      self.profile_links = []    #URLs for other profiles of the same person.
      self.email_addresses = []  #Email addresses for this profile.
      self.phone_numbers = []    #Phone numbers for this profile.

      #Biographical
      self.names = []        #UIDs or usernames for this profile.
      self.self_descriptions = []#Self-descriptive texts.
      self.age = 0               #Person's reported age.
      self.tags = []             #Textual tags describing the person.
      self.education = []        #Strings listing educational institutions, in order.
      self.occupation = None       #Current occupation.
      self.gender = None           #The reported gender.
      self.relationship_status = []#A person's marital or relationship status.
      self.sexual_orientation = []#A person's reported orientation.
      self.verified = False      #Whether the network has vetted this profile for accuracy.
      self.religion = None         #The described religion.
      self.physical = None       #A physical description of the person holding the profile.
      self.habits = []           #A list of habits the profile identifies its owner as having.

      #Visual
      self.profile_images = []   #Links to the main avatars of the profile. (Downloaded?)
      self.banners = []          #Links to the personal header or background images.
      self.tagged_photos = []    #Images linked to this profile by this or other users.

      #Opinion
      self.content_opinion = []  #Opinion ratings of in-network user content, {link:opinion}
      self.brand_opinion = []    #Opinion ratings of in-network brand/corporate content.
      self.other_opinion = []    #Opinion ratings of off-network content.
      
      #Temporal
      self.activity_timestamps = []#list of activity times.
      self.membership_date = None  #Date/time the user joined the network (estimated from timestamps if possible)
      self.last_seen = None        #Date/time the user was last seen by the network (estimated if necessary/possible).

      #Geographical
      self.current_location = None #Current lat/long
      self.location_set = []       #Set of all locations associated with the profile.
      self.location_history = []   #{location:time} for each location (generates location_set as well).

      #Degree
      self.subscribers = 0         #Number of people following this profile.
      self.subscribed = 0          #Number of people this user follows.
      self.contributions = 0       #Number of contribution made to the network.
      self.visibility = 0          #Number of views of this profile.
      self.reputation = None       #This user's reputation as rated by others.
      self.trophies = []           #Custom award tags this user has unlocked.
      self.rank = None             #This user's rank in the community, as expressed in tiered levels.

      #Relationships
      self.interacted = []         #Links to profiles interacted with.
      self.followers = []          #Links to profiles of followers.
      self.followed_by = []        #Links to profiles which this user follows.
      self.grouped = []            #Links to profiles this user is grouped with.

      self.brands_followed = []    #Links to profiles of brands this user follows.
      self.contributor = []        #Links to profiles of brands this user contributes to.

      self.content = []            #List of content items


def my_import(name):
  """ Helper function courtesy of  __import__ python docs.

  :param str name: Name of module to import.
  :return: imported module. """
  mod = __import__(name)
  components = name.split('.')
  for comp in components[1:]:
      mod = getattr(mod, comp)
  return mod


class Analyser:
  
  network_name = "None"
  
  def __init__(self,profilestore,logger,namesfile=None):
    self.profilestore = profilestore
    self.namesfh = None
    if namesfile:
      self.namesfh = open(namesfile, 'a')
    if not logger:
      logger = common.logger.getLogger(self.__class__.__name__)   
    self.imagestore = common.imagestore.ImageStore('images',logger)
    self.logger = logger
    self.modules = self.__load_modules()
    

  def __load_modules(self):
    modules = []
    for fn in os.listdir('.'):
      if os.path.isdir(fn) and fn not in ['common'] and 'core.py' in os.listdir(fn):
        fp = fn+'.core'
        self.logger.info("Loading module from {}".format(fp))
        modules.append(my_import(fp))
    self.logger.info("Loaded {} modules.".format(len(modules)))
    return modules
        
  def analyse(self,response_dict,record):
    raise NotImplementedError("'analyse()' not implemented for `{}`".format(self.__class__.__name__))

  def url_to_record(self, url, name):
    for module in self.modules:
      if module.is_valid_result(self, url):
        record = {}
        record['network'] = module.network_name
        record['network_id'] = module.get_net_id(self, url)
        record['url'] = url
        record['search_term'] = name
        return record
    return None 

  def store(self, profile, filepath):
    pickle.dump(profile, open(filepath,'wb'))

  def run(self,indirpath='raw',outdirpath='profiles'):

    if not os.path.exists(outdirpath):
      os.makedirs(outdirpath)

    names = set()

    for record in self.profilestore.records:
      fname = str(record['uid'])+'.json'

      if record['network'] == self.network_name and os.path.exists(indirpath+os.sep+fname):
        self.logger.info("Analysing {}".format(fname))
        response_obj = json.load(open(indirpath+os.sep+fname,'r'))
        profile = self.analyse(response_obj,record)

        if self.namesfh:
          #If we're building a name-list (G+ only, usually), add it here.
          names.add(profile.bestname())

        self.store(profile, outdirpath+os.sep+str(record['uid'])+'.pickle')

        for link in profile.profile_links:
          rec = self.url_to_record(link, profile.bestname())
          if rec:
            lid = self.profilestore.add_record(rec)
            self.profilestore.add_match(record['uid'], lid)
          else:
            self.logger.info("Link {} failed to translate into a record.".format(link))

    if self.namesfh:
    #Write names file. 
      for name in names:
        if name:
          self.namesfh.write(name+'\n')
