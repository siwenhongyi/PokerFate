---@class SdkModel
local P = class("SdkModel", BaseModel)

function P:ctor()
    self.saveData = {
        cloud = {
            adjustId = "",
        }
    }

    P.super.ctor(self)
end

function P:afterInit()
    self:checkSdk()
end

function P:checkSdk()
    self:checkAdjust()
end

function P:getAdjustCache()
    if self.cloud.adjustId == "" then
        self:tryGetAdjust()
    end
    return self.saveData.cloud.adjustId
end

function P:checkAdjust()
    self:tryGetAdjust()
    --更新4次都没有就不更新了
    bee.repeatN(30, 0.05, function()
        self:tryGetAdjust()
    end)
end

function P:tryGetAdjust()
    if self.saveData.cloud.adjustId ~= "" then
        return self.saveData.cloud.adjustId
    end
    self.saveData.cloud.adjustId = CS.SdkHelper.GetAdjustID()
    if self.saveData.cloud.adjustId ~= "" then
        bee.emit("evt_onAdjustId", self.saveData.cloud.adjustId)
    end
    return self.saveData.cloud.adjustId
end

