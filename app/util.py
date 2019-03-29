from app import mongo
from bson.objectid import ObjectId


def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc


def get_manager_profile(manager):

    ret = mongo.db.users.find_one({
        "_id": ObjectId(manager["_id"])
    })
    # del ret["_id"]
    if "managers" in ret:
        del ret["managers"]
    if "password" in ret:
        del ret["password"]
    if "username" in ret:
        del ret["username"]
    if "kpi_id" in ret:
        del ret["kpi_id"]
    ret['_id'] = str(ret['_id'])
    if "weight" in ret:
        ret["weight"] = manager["weight"]
    return ret
