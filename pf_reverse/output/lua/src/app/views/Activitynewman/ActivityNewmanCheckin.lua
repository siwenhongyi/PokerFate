local P = class("ActivityNewmanCheckin", UiBase)

function P:onAwake()
    self.GoldItem = self:find("AnimRoot/RightTop/GoldItem")
end

function P:onShow()
    bee.invoke(self.GoldItem, "setItemId", GPropId.Gold)
    self:evt_refreshTopInfo()
end

function P:evt_refreshTopInfo()
    bee.invoke(self.GoldItem, "setCount", _N(PlayerModel:getGold()))
end

return P