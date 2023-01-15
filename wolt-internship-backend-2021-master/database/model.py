from .db import db
###############################################################################################
# launch_date is converted to DateTimeField format for easy manipulation
# location is stored as a GeoJSON object (in PointField format) for easy storage & manipulation
###############################################################################################
class Restaurants(db.Document):
    blurhash        = db.StringField(required = True)
    launch_date     = db.DateTimeField(required = True)
    location        = db.PointField(required = True)
    name            = db.StringField(required = True)
    online          = db.BooleanField(required = True)
    popularity      = db.FloatField(required = True)
