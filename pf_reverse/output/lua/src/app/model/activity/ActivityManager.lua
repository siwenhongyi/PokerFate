local P = class("ActivityManager", BaseModel)

function P:ctor()
    self._actMap = {}
    P.super.ctor(self)
end

function P:addModel(actModel)
    self._actMap[actModel:getActivityId()] = actModel
end

-- 获取已开放的活动列表
function P:getOpenActivities(actType)
    local actList = {}
    for _, v in ipairs(self._actMap) do
        if v:isActivityOpen() and (not actType or v:getActivityType() == actType) then
            table.insert(actList, v)
        end
    end
    return actList
end

function P:isActivityOpen(actId, subId)
    if actId and self._actMap[actId] then
        return self._actMap[actId]:isActivityOpen(subId)
    end
    return false
end

function P:getActivityEndTime(actId, subId)
    if actId and self._actMap[actId] then
        return self._actMap[actId]:getEndTime(subId)
    end
    return 0
end

function P:reqActivityData()
    for _, v in pairs(self._actMap) do
        v:reqActivityData()
    end
end

return P