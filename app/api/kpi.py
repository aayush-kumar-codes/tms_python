from app import token
from app import mongo
from flask import (
    Blueprint, flash, jsonify, abort, request
)

from bson.objectid import ObjectId


from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    get_jwt_identity, get_current_user, jwt_refresh_token_required,
    verify_jwt_in_request
)

bp = Blueprint('kpi', __name__, url_prefix='/kpi')


@bp.route('', methods=['POST', 'GET'])
@bp.route('/<string:id>', methods=['PUT', 'DELETE'])
@jwt_required
@token.admin_required
def kpi(id=None):
    if request.method == "GET":
        docs = mongo.db.kpi.find({})
        kpis = []
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            kpis.append(doc)
        return jsonify(kpis), 200

    if request.method == "DELETE":
        return jsonify(mongo.db.kpi.remove({
            "_id": ObjectId(id)
        }))

    if not request.json:
        abort(500)

    kpi_name = request.json.get('kpi_name', None)
    kpi_json = request.json.get('kpi_json', None)
    kra_json = request.json.get('kra_json', None)

    if kpi_json is None or kpi_name is None:
        return jsonify(msg="Invalid request"), 400

    if request.method == "POST":
        kpi = mongo.db.kpi.insert_one({
            "kpi_name": kpi_name,
            "kpi_json": kpi_json,
            "kra_json": kra_json
        })
        return jsonify(str(kpi.inserted_id)), 200
    elif request.method == "PUT":
        if id is None:
            return jsonify(msg="Invalid request"), 400

        kpi = mongo.db.kpi.update({
            "_id": ObjectId(id)
        },
            {
            "$set": {
                "kpi_name": kpi_name,
                "kpi_json": kpi_json,
                "kra_json": kra_json
            }
        }, upsert=False)

        return jsonify(kpi), 200
    
@bp.route('/era', methods=['POST', 'GET'])
@bp.route('/era/<string:id>', methods=['PUT', 'DELETE'])
@jwt_required
@token.admin_required
def era(id=None):
    if request.method == "GET":
        docs = mongo.db.era.find({})
        era = []
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            era.append(doc)
        return jsonify(era), 200

    if request.method == "DELETE":
        return jsonify(mongo.db.era.remove({
            "_id": ObjectId(id)
        }))

    if not request.json:
        abort(500)

    era_name = request.json.get('era_name', None)
    era_json = request.json.get('era_json', None)

    if era_json is None or era_name is None:
        return jsonify({"msg": "Invalid request"}), 400

    if request.method == "POST":
        era = mongo.db.era.insert_one({
            "era_name": era_name,
            "era_json": era_json
        })
        return jsonify(str(era.inserted_id)), 200
    elif request.method == "PUT":
        if id is None:
            return jsonify({"msg": "Invalid request"}), 400

        era = mongo.db.era.update({
            "_id": ObjectId(id)
        },
            {
            "$set": {
                "era_name": era_name,
                "era_json": era_json
            }
        }, upsert=False)
        return jsonify(era), 200


@bp.route("/assign_era/<string:user_id>/<string:era_id>", methods=["GET"])
@jwt_required
@token.admin_required
def assign_era_to_user(user_id, era_id):
    if era_id == -1:
        ret = mongo.db.users.update({
            "_id": ObjectId(user_id)
        }, {
            "$unset": {
                "era_id": ""
            }
        })
    else:
        ret = mongo.db.users.update({
            "_id": ObjectId(user_id)
        }, {
            "$set": {
                "era_id": era_id
            }
        })
    return jsonify(ret), 200


@bp.route("/assign_kpi/<string:user_id>/<string:kpi_id>", methods=["GET"])
@jwt_required
@token.admin_required
def assign_kpi_to_user(user_id, kpi_id):
    if kpi_id == -1:
        ret = mongo.db.users.update({
            "_id": ObjectId(user_id)
        }, {
            "$unset": {
                "kpi_id": ""
            }
        })
    else:
        ret = mongo.db.users.update({
            "_id": ObjectId(user_id)
        }, {
            "$set": {
                "kpi_id": kpi_id
            }
        })
    return jsonify(ret), 200


@bp.route("/assign_manager/<string:user_id>/<string:manager_id>/<int:weight>", methods=["GET"])
@jwt_required
@token.admin_required
def assign_manager(user_id, manager_id, weight):
    if weight > 0:
        ret = mongo.db.users.find_one({
            "_id": ObjectId(manager_id)
        })
        if "role" in ret and (ret["role"] == "manager" or ret["role"] == "admin"):
            ret = mongo.db.users.update({
                "_id": ObjectId(user_id)
            }, {
                "$push": {
                    "managers": {
                        "_id": manager_id,
                        "weight": weight
                    }
                }
            })
        else:
            return jsonify(msg="user should be a manger"), 500
    else:
        ret = mongo.db.users.update({
            "_id": ObjectId(user_id)
        }, {
            "$pull": {
                "managers": {
                    "_id": manager_id
                }
            }
        })
    return jsonify(ret), 200
