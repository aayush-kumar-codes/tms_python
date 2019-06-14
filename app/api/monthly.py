from app import token
from app import mongo
from app.util import serialize_doc, get_manager_profile
from flask import (
    Blueprint, flash, jsonify, abort, request
)
import requests
from app.config import attn_url, secret_key
import json
import dateutil.parser
from bson.objectid import ObjectId

from app.util import slack_message, slack_msg
from app.config import slack_token
from slackclient import SlackClient

import datetime
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    get_jwt_identity, get_current_user, jwt_refresh_token_required,
    verify_jwt_in_request
)
from app.config import slack_token

bp = Blueprint('monthly', __name__, url_prefix='/')


def get_manager_juniors(id):
    users = mongo.db.users.find({
        "managers": {
            "$elemMatch": {"_id": str(id)}
        }
    })
    user_ids = []
    for user in users:
        user_ids.append(str(user['_id']))
    return user_ids


def load_checkin(id):
    ret = mongo.db.reports.find_one({
        "_id": ObjectId(id)
    })
    return serialize_doc(ret)


def load_all_checkin(all_chekin):
    today = datetime.datetime.utcnow()
    last_monday = today - datetime.timedelta(days=(today.weekday() + 8))
    ret = mongo.db.reports.find({
        "user": all_chekin,
        "type": "daily",
        "created_at": {
            "$gte": datetime.datetime(last_monday.year, last_monday.month, last_monday.day)}
    })
    ret = [serialize_doc(doc) for doc in ret]
    return ret


def add_checkin_data(weekly_report):
    select_days = weekly_report["select_days"]
    select_days = [load_checkin(day) for day in select_days]
    all_chekin = weekly_report['user']
    print(all_chekin)
    all_chekin = (load_all_checkin(all_chekin))

    weekly_report["select_days"] = select_days
    weekly_report['all_chekin'] = all_chekin
    return weekly_report


def load_kpi(kpi_data):
    print(kpi_data)
    ret = mongo.db.kpi.find_one({
        "_id": ObjectId(kpi_data)
    })
    return serialize_doc(ret)


def add_kpi_data(kpi):
    if "kpi_id" in kpi:
        data = kpi["kpi_id"]
        kpi_data = (load_kpi(data))
        kpi['kpi_id'] = kpi_data
    else:
        kpi['kpi_id'] = ""
    return kpi


def load_all_weekly(all_weekly):
    ret = mongo.db.reports.find({
        "user": all_weekly,
        "type": "weekly"
    })
    ret = [serialize_doc(doc) for doc in ret]
    return ret


def load_user(user):
    ret = mongo.db.users.find_one({
        "_id": ObjectId(user)
    }, {"profile": 0})
    return serialize_doc(ret)


def add_user_data(user):
    user_data = user['user']
    user_data = (load_user(user_data))
    user['user'] = user_data
    return user


def load_manager(manager):
    ret = mongo.db.users.find_one({
        "_id": manager
    }, {"profile": 0})
    return serialize_doc(ret)


def add_manager_data(manager):
    for elem in manager['review']:
        elem['manager_id'] = load_manager(ObjectId(elem['manager_id']))
    return manager


def load_details(data):
    user_data = data['user']
    all_weekly = data['user']
    all_weekly = (load_all_weekly(all_weekly))
    user_data = (load_user(user_data))
    data['user'] = user_data
    if 'review' in data:
        review_detail = data['review']
    else:
        review_detail = None
    if review_detail is not None:
        for elem in review_detail:
            elem['manager_id'] = load_manager(ObjectId(elem['manager_id']))
    data['all_weekly'] = all_weekly
    return data


def no_review(data):
    user_data = data['user']
    user_data = (load_user(user_data))
    data['user'] = user_data
    review_data = None
    data['review'] = review_data
    return data


# Api for delete monthly report
@bp.route('/delete_monthly/<string:monthly_id>', methods=['DELETE'])
@jwt_required
def delete_monthly(monthly_id):
    current_user = get_current_user()
    docs = mongo.db.reports.remove({
        "_id": ObjectId(monthly_id),
        "type": "monthly",
        "user": str(current_user['_id'])
    })
    return jsonify(str(docs)), 200


# Api for monthly checkin
@bp.route('/monthly', methods=["POST", "GET"])
@jwt_required
def add_monthly_checkin():
    today = datetime.datetime.utcnow()
    month = today.strftime("%B")
    current_user = get_current_user()
    doj = str(current_user['dateofjoining'])
    slack = current_user['slack_id']
    date = datetime.datetime.strptime(doj, "%Y-%m-%d %H:%M:%S")
    datee = date.day
    if request.method == "GET":
        report = mongo.db.reports.find({
            "user": str(current_user["_id"]),
            "type": "monthly",
            "month": month
        })
        report = [add_user_data(serialize_doc(doc)) for doc in report]
        return jsonify(report)
    else:
        if datee > 7:
            join_date = datee - 7
        else:
            join_date = datee

        print(join_date)
        today_date = int(today.strftime("%d"))
        print(today_date)
        if today_date > join_date:
            if not request.json:
                abort(500)
            report = request.json.get("report", [])
            reviewed = False
            users = mongo.db.users.find({
                "_id": ObjectId(current_user["_id"])
            })
            users = [serialize_doc(doc) for doc in users]
            managers_data = []
            for data in users:
                for mData in data['managers']:
                    mData['reviewed'] = reviewed
                    managers_data.append(mData)
            rep = mongo.db.reports.find_one({
                "user": str(current_user["_id"]),
                "type": "monthly",
                "month": month,
            })
            if rep is not None:
                return jsonify({"msg": "You have already submitted your monthly report"}), 409
            else:
                ret = mongo.db.reports.insert_one({
                    "user": str(current_user["_id"]),
                    "created_at": datetime.datetime.utcnow(),
                    "type": "monthly",
                    "is_reviewed": managers_data,
                    "report": report,
                    "month": month
                }).inserted_id
                slack_message(msg="<@" + slack + ">!" + ' ''have created monthly report')
                return jsonify(str(ret)), 200
        else:
            return jsonify({"msg": "Your date of joining is " + str(datee) +
                                   " you can submit your monthly report after " + str(join_date) +
                                   "th of this month"}), 405


@bp.route("/manager_monthly_all", methods=["GET"])
@jwt_required
@token.manager_required
def get_manager_monthly_list_all():
    current_user = get_current_user()
    juniors = get_manager_juniors(current_user['_id'])
    print(juniors)
    docs = mongo.db.reports.find({
        "type": "monthly",
        "user": {
            "$in": juniors
        }
    }).sort("created_at", 1)
    docs = [load_details(serialize_doc(doc)) for doc in docs]
    return jsonify(docs), 200


@bp.route("/manager_monthly/<string:monthly_id>", methods=["POST"])
@jwt_required
@token.manager_required
def get_manager_monthly_list(monthly_id):
    current_user = get_current_user()
    manager_name = current_user['username']
    if not request.json:
        abort(500)
    comment = request.json.get("comment", None)

    if monthly_id is None:
        return jsonify(msg="invalid request"), 500
    juniors = get_manager_juniors(current_user['_id'])

    dab = mongo.db.reports.find({
        "_id": ObjectId(monthly_id),
        "type": "monthly",
        "is_reviewed": {'$elemMatch': {"_id": str(current_user["_id"]), "reviewed": False}},
        "user": {
            "$in": juniors
        }
    }).sort("created_at", 1)
    dab = [serialize_doc(doc) for doc in dab]
    for data in dab:
        ID = data['user']
        rap = mongo.db.users.find({
            "_id": ObjectId(str(ID))
        })
        rap = [serialize_doc(doc) for doc in rap]
        for dub in rap:
            junior_name = dub['username']
            sap = mongo.db.reports.find({
                "_id": ObjectId(monthly_id),
                "review": {'$elemMatch': {"manager_id": str(current_user["_id"])},
                           }
            })
            sap = [serialize_doc(saps) for saps in sap]
            if not sap:
                ret = mongo.db.reports.update({
                    "_id": ObjectId(monthly_id)
                }, {
                    "$push": {
                        "review": {
                            "created_at": datetime.datetime.utcnow(),
                            "comment": comment,
                            "manager_id": str(current_user["_id"])
                        }
                    }
                })
                docs = mongo.db.reports.update({
                    "_id": ObjectId(monthly_id),
                    "is_reviewed": {'$elemMatch': {"_id": str(current_user["_id"]), "reviewed": False}},
                }, {
                    "$set": {
                        "is_reviewed.$.reviewed": True
                    }})
                dec = mongo.db.recent_activity.update({
                    "user": str(ID)},
                    {"$push": {
                        "report_reviewed": {
                            "created_at": datetime.datetime.now(),
                            "priority": 0,
                            "Message": "Your monthly report has been reviewed by "" " + manager_name
                        }}}, upsert=True)
                # slack_message(msg=junior_name + " " + 'your monthly report is reviewed by' + ' ' + manager_name)
                return jsonify(str(ret)), 200
            else:
                return jsonify(msg="Already reviewed this report"), 400


@bp.route('/skip_review/<string:weekly_id>', methods=['POST'])
@jwt_required
@token.manager_required
def skip_review(weekly_id):
    current_user = get_current_user()
    doj = current_user['dateofjoining']
    print(doj)
    reports = mongo.db.reports.find({
        "_id": ObjectId(weekly_id),
        "is_reviewed": {'$elemMatch': {"_id": str(current_user["_id"])}
                        }
    })
    reports = [serialize_doc(doc) for doc in reports]
    manager_id = []
    for data in reports:
        for elem in data['is_reviewed']:
            manager_id.append(ObjectId(elem['_id']))
    managers = mongo.db.users.find({
        "_id": {"$in": manager_id}
    })
    managers = [serialize_doc(doc) for doc in managers]
    join_date = []
    for dates in managers:
        join_date.append(dates['dateofjoining'])
    if len(join_date) > 1:
        oldest = min(join_date)
        if doj == oldest:
            rep = mongo.db.reports.update({
                "_id": ObjectId(weekly_id),
                "is_reviewed": {'$elemMatch': {"_id": str(current_user["_id"])}},
            }, {
                "$pull": {
                    "is_reviewed": {"_id": str(current_user["_id"])}
                }}, upsert=False)
            return jsonify(str(rep))
        else:
            return jsonify({"msg": "You cannot skip this report review"}), 400
    else:
        return jsonify({"msg": "You cannot skip this report review as you are the only manager"}), 400


@bp.route('/delete_manager_monthly_response/<string:manager_id>', methods=['DELETE'])
@jwt_required
@token.manager_required
def delete_manager_monthly_response(manager_id):
    current_user = get_current_user()
    today = datetime.datetime.utcnow()
    last_day = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    next_day = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    report = mongo.db.reports.find_one({
        "_id": ObjectId(manager_id),
        "review": {'$elemMatch': {"manager_id": str(current_user["_id"]), "created_at": {
            "$gte": last_day,
            "$lte": next_day}}
                   }})
    print(report)
    if report is not None:
        ret = mongo.db.reports.update({
            "_id": ObjectId(manager_id)}
            , {
                "$pull": {
                    "review": {
                        "manager_id": str(current_user["_id"]),
                    }
                }})
        docs = mongo.db.reports.update({
            "_id": ObjectId(manager_id),
            "is_reviewed": {'$elemMatch': {"_id": str(current_user["_id"]), "reviewed": True}},
        }, {
            "$set": {
                "is_reviewed.$.reviewed": False
            }})
        return jsonify(str(docs)), 200
    else:
        return jsonify({"msg": "You can no longer delete your submitted report"}), 400


def details_manager(data):
    user_data = data['user']
    user_data = (load_user(user_data))
    data['user'] = user_data
    if 'review' in data:
        review_detail = data['review']
    else:
        review_detail = None
    if review_detail is not None:
        for elem in review_detail:
            elem['manager_id'] = load_manager(ObjectId(elem['manager_id']))
    return data


@bp.route('/junior_monthly_report', methods=['GET'])
@jwt_required
@token.manager_required
def junior_monthly_report():
    current_user = get_current_user()
    users = mongo.db.users.find({
        "managers": {
            "$elemMatch": {"_id": str(current_user['_id'])}
        }
    }, {"profile": 0})
    users = [serialize_doc(ret) for ret in users]
    ID = []
    for data in users:
        ID.append(data['_id'])
    print(ID)
    reports = mongo.db.reports.find({
        "user": {"$in": ID},
        "type": "monthly",
        "is_reviewed": {'$elemMatch': {"_id": str(current_user["_id"]), "reviewed": False}}
    }).sort("created_at", 1)
    reports = [no_review(serialize_doc(doc)) for doc in reports]
    report = mongo.db.reports.find({
        "user": {"$in": ID},
        "type": "monthly",
        "is_reviewed": {'$elemMatch': {"_id": str(current_user["_id"]), "reviewed": True}}
    }).sort("created_at", 1)
    report = [details_manager(serialize_doc(doc)) for doc in report]
    report_all = reports + report

    return jsonify(report_all)


@bp.route('/skip_review/<string:monthly_id>', methods=['POST'])
@jwt_required
@token.manager_required
def skip_review(monthly_id):
    current_user = get_current_user()
    doj = current_user['dateofjoining']
    print(doj)
    reports = mongo.db.reports.find({
        "_id": ObjectId(monthly_id),
        "is_reviewed": {'$elemMatch': {"_id": str(current_user["_id"])}
                        }
    })
    reports = [serialize_doc(doc) for doc in reports]
    manager_id = []
    for data in reports:
        for elem in data['is_reviewed']:
            manager_id.append(ObjectId(elem['_id']))
    managers = mongo.db.users.find({
        "_id": {"$in": manager_id}
    })
    managers = [serialize_doc(doc) for doc in managers]
    join_date = []
    for dates in managers:
        join_date.append(dates['dateofjoining'])
    if len(join_date) > 1:
        oldest = min(join_date)
        if doj == oldest:
            rep = mongo.db.reports.update({
                "_id": ObjectId(monthly_id),
                "is_reviewed": {'$elemMatch': {"_id": str(current_user["_id"])}},
            }, {
                "$pull": {
                    "is_reviewed": {"_id": str(current_user["_id"])}
                }}, upsert=False)
            return jsonify(str(rep))
        else:
            return jsonify({"msg": "You cannot skip this report review"}), 400
    else:
        return jsonify({"msg": "You cannot skip this report review as you are the only manager"}), 400