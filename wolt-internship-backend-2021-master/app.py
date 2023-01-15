from flask import Flask, jsonify, request, Response, json
from database.model import Restaurants
from database.db import initialize_db
from mongoengine.queryset.visitor import Q
import datetime
import dateutil.relativedelta
from itertools import chain

app = Flask(__name__)

###############################################################
# Database Configuration & Initialization
app.config['MONGODB_SETTINGS'] = {
    'host':'mongodb://mongo:27017/wolt-db'
}
db = initialize_db(app)
#Clearing the Collection
#Else every time 'docker-compose up' is run without pruning, the collection will be populated with redundant entries, resulting in improper results
Restaurants.drop_collection()
###############################################################

###############################################################
# Reading the data in json file to populate the collection 'restaurants'
with open('restaurants.json') as file:
    data = json.load(file)
data = data['restaurants']

# Populating the collection
# Refer to 'model.py' to understand the collection's structure & field types
for restaurant in data:
    entry = Restaurants(blurhash   = restaurant['blurhash'],
                        launch_date = restaurant['launch_date'],
                        location    = {'type': 'Point', 'coordinates': restaurant['location']},
                        name        = restaurant['name'],
                        online      = restaurant['online'],
                        popularity  = restaurant['popularity']
                       )
    entry.save()
###############################################################

###############################################################
# Root
@app.route('/')
def get_route():
    output = {'message': 'It looks like you are trying to access FlaskAPP over HTTP on the native driver port.'}
    return output, 200

# API Endpoint - discovery
# Refer the problem statement for the required logic
@app.route('/discovery', methods = ['GET'])
def get_discovery():
    """
    Input : Latitude & Longitude of customer location as request parameters
    Output: Page (JSON response) containing most popular, newest, and nearby restaurants
    Logic : Extensive - refer problem statement
    """
    # Extracting the customer's location & handling exceptions
    try:
        customer_lat = float(request.args.get('lat'))
        customer_lon = float(request.args.get('lon'))
        if type(customer_lat) != float or type(customer_lon) != float:
            raise Exception
        if customer_lat < -90 or customer_lat > 90 or customer_lon < -180 or customer_lon > 180:
            raise Exception
    except:
        output = {'message': 'Oops! Missing request parameters or Improper data type(s) and/or out of bound value(s) encountered in request parameters.'}
        return output, 400
    customer_loc = [customer_lon, customer_lat]

    # Initializing the lists of final entries to be displayed
    nearby_restaurants = []
    new_restaurants    = []
    popular_restaurants= []

    # Gathering all online restaurants in a 1.5 km radius
    # Results are sorted ascending (nearest to farthest) as a property of __near
    # Excluding the documents' ids from the results
    online_restaurants = Restaurants.objects(Q(location__near = customer_loc, location__max_distance = 1500) & Q(online = True))
    online_restaurants = online_restaurants.exclude("id")

    # Gathering all offline (closed) restaurants in a 1.5 km radius
    # Results are already sorted ascending (nearest to farthest) as a property of __near
    # Excluding the documents' ids from the results
    offline_restaurants = Restaurants.objects(Q(location__near = customer_loc, location__max_distance = 1500) & Q(online = False))
    offline_restaurants = offline_restaurants.exclude("id")

    #######################################################################################
    # NEARBY RESTAURANTS -> Max. 10
    # nearby_restaurants will be a list of Python dicts
    # Python dicts because formats of launch_date and location from the database need to be changed (refer lines 107-110)
    # If there are sufficient restaurants 'online' nearby (refer line 78), display the top 10
    if len(online_restaurants) >= 10 :
        nearby_restaurants = json.loads(online_restaurants[:10].to_json())
    # If not, then cover the difference of upto 10 maximum from the nearby 'offline' restaurants (refer line 84)
    elif len(online_restaurants) < 10:
        difference = 10 - len(online_restaurants)
        online_restaurants_1 = json.loads(online_restaurants.to_json())
        if difference >= len(offline_restaurants):
            offline_restaurants_1= json.loads(offline_restaurants.to_json())
            nearby_restaurants = list(chain(online_restaurants_1, offline_restaurants_1))
        elif difference < len(offline_restaurants):
            offline_restaurants_1 = json.loads(offline_restaurants[:difference].to_json())
            nearby_restaurants = list(chain(online_restaurants_1, offline_restaurants_1))

    # Converting the launch-date from a DataTimeField object to YYYY-mm-dd format string
    # Converting the location from a GeoJSON (PointField) object to a list containing the coordinates
    for i in nearby_restaurants:
        s = i['launch_date']['$date']/1000
        i['launch_date'] = datetime.datetime.fromtimestamp(s).strftime("%Y-%m-%d")
        i['location']    = i['location']['coordinates']
    #######################################################################################

    #######################################################################################
    # POPULAR RESTAURANTS - Max. 10
    # Sorting the online_restaurants (refer line 78) by popularity in a descending fashion
    popular_online = online_restaurants.order_by('-popularity')

    # Sorting the offline_restaurants (refer line 84) by popularity in a descending fashion
    popular_offline = offline_restaurants.order_by('-popularity')

    # popular_restaurants will be a list of Python dicts
    # Python dicts because formats of launch_date and location from the database need to be changed (refer lines 139-142)
    # If there are sufficient popular_online restaurants, display the top 10
    if len(popular_online) >= 10 :
        popular_restaurants = json.loads(popular_online[:10].to_json())
    # If not, then cover the difference of upto 10 maximum from the popular_offline restaurants
    elif len(popular_online) < 10:
        difference = 10 - len(popular_online)
        popular_online_1 = json.loads(popular_online.to_json())
        if difference >= len(popular_offline):
            popular_offline_1 = json.loads(popular_offline.to_json())
            popular_restaurants = list(chain(popular_online_1,popular_offline_1))
        elif difference < len(popular_offline):
            popular_offline_1 = json.loads(popular_offline[:difference].to_json())
            popular_restaurants = list(chain(popular_online_1,popular_offline_1))

    # Converting the launch-date from a DataTimeField object to YYYY-mm-dd format string
    # Converting the location from a GeoJSON (PointField) object to a list containing the coordinates
    for i in popular_restaurants:
        s = i['launch_date']['$date']/1000
        i['launch_date'] = datetime.datetime.fromtimestamp(s).strftime("%Y-%m-%d")
        i['location']    = i['location']['coordinates']
    #####################################################################################

    #####################################################################################
    # NEW RESTAURANTS - Max. 10
    # Computing the date 4 months ago from today, and converting it to YYYY-mm-dd
    date_today = datetime.date.today()
    date_threshold = date_today - dateutil.relativedelta.relativedelta(months = 4)
    date_threshold = date_threshold.strftime("%Y-%m-%d")

    # Finding 'online' restaurants (refer line 78) with less than 4 months old launch_date
    new_online = online_restaurants.order_by('-launch_date')
    new_online = new_online.filter(launch_date__gte = date_threshold)

    # Finding 'offline' restaurants (refer line 84) with less than 4 months old launch_date
    new_offline = offline_restaurants.order_by('-launch_date')
    new_offline = new_offline.filter(launch_date__gte = date_threshold)

    # new_restaurants will be a list of Python dicts
    # Python dicts because formats of launch_date and location from the database need to be changed (refer lines 179-182)
    # If there are sufficient new_online, display the top 10
    if len(new_online) >= 10 :
        new_restaurants = new_online[:10]
        new_restaurants = json.loads(new_restaurants.to_json())
    # If not, then cover the difference of upto 10 maximum from new_offline
    elif len(new_online) < 10:
        difference = 10 - len(new_online)
        new_online_1 = json.loads(new_online.to_json())
        if difference >= len(new_offline):
            new_offline_1 = json.loads(new_offline.to_json())
            new_restaurants = list(chain(new_online_1, new_offline_1))
        elif difference < len(new_offline):
            new_offline_1 = json.loads(new_offline[:difference].to_json())
            new_restaurants = list(chain(new_online_1, new_offline_1))

    # Converting the launch-date from a DataTimeField object to YYYY-mm-dd format string
    # Converting the location from a GeoJSON (PointField) object to a list containing the coordinates
    for i in new_restaurants:
        s = i['launch_date']['$date']/1000
        i['launch_date'] = datetime.datetime.fromtimestamp(s).strftime("%Y-%m-%d")
        i['location']    = i['location']['coordinates']

    # Preparing the JSON output
    output = json.dumps({"sections":[
                          {"title": "Popular Restaurants", "restaurants": popular_restaurants},
                          {"title": "New Restaurants", "restaurants": new_restaurants},
                          {"title": "Nearby Restaurants", "restaurants": nearby_restaurants}
                         ]
                        }, sort_keys = False)

    return output, 200
