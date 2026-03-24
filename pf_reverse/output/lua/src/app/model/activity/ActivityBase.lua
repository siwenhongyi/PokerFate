local P = class("ActivityBase", BaseModel)

function P:ctor(actId, actType)
    P.super.ctor(self)

    self._actId = actId
    self._actType = actType
    if not self._actId or not self._actType then
        printError("ActivityBase:ctor missing actId or actType " .. debug.traceback())
    end
end

function P:afterInit()
    ActivityManager:addModel(self)
end

function P:getActivityId()
    return self._actId
end

function P:getActivityType()
    return self._actType
end

function P:isActivityOpen()
    return false
end

function P:refreshReddot()
end

-- 请求活动数据
function P:reqActivityData()
end

