local P = class("ClientDataModel", BaseModel)

-- 前端存储在服务器的数据
function P:ctor()
    self.saveData = {}

    P.super.ctor(self)

    --[[
    {
        "play_DevelopmentFund_story": 1,    -- 返利基金是否已经播放过剧情了
    }
    ]]
    self._datas = {}

    self._fundStatus = 0    -- 返利基金状态，0=未结算或无可领奖励，1=已结算或有可领奖励
end

function P:afterLogin()
    self._datas = {}
    self._fundStatus = 0
end

function P:initDatas(dataStr)
    if dataStr and dataStr ~= "" then
        self._datas = json.decode(dataStr) or {}
        if type(self._datas) ~= "table" then
            self._datas = {}
        end
    else
        self._datas = {}
    end

    self:refreshReddot()
end

function P:refreshReddot()
    local DevelopmentFundRed = self._fundStatus == 1 and 1 or 0
    if not self:getData("play_DevelopmentFund_story") then
        DevelopmentFundRed = 1
    end
    RedManager:addTagWithNum(DevelopmentFundRed, RedTag.DevelopmentFund)
end

function P:getData(key)
    return self._datas[key]
end

function P:setData(key, value)
    if self._datas[key] ~= value then
        self._datas[key] = value
        self._isDirty = true

        self:refreshReddot()
    end
end

function P:doSave()
	if self._isDirty then
        self._isDirty = false
        local jstr = json.encode(self._datas)
        Net:sendReq("pb.SetClientDefStrREQ", {client_def_str = jstr})
    end
	return false
end

function P:reqData()
    self:reqDevelopmentFundData()
end

------------------ 返利基金 ------------------
function P:reqDevelopmentFundData()
    Net:post("/activity/rebateStatus", {t = 1}, function(data)
        if data.code == 0 then
            self._fundStatus = data.status
            self:refreshReddot()
        end
    end)
end

return P