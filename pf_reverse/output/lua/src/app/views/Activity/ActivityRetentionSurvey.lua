local P = class("ActivityRetentionSurvey", UiBase)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")
    self.rewardRoot = self:find("Items", self.Center)
    self.item = self:find("Item1", self.Center)
    self.item:SetActive(false)

    self.ClaimedButton = self:find("ClaimedButton", self.Center)
    self.ClaimButton = self:find("ClaimButton", self.Center)
    self.EnterButton = self:find("EnterButton", self.Center)

    self.questionData = ActivityModel:getQuestionData()
end

function P:onShow()
    local rewards = self.questionData.rewards
    local rewardCount = #rewards
    for i = 1, rewardCount do
        local index = i
        local propCfg = tpl_props[rewards[index].item_id]
        local item = CU.GameObject.Instantiate(self.item, self.rewardRoot.transform, false)
        item:SetActive(true)
        bee.setIcon(self:find("frame", item), string.format("Common[common_item_grid_m_%02d]", propCfg.quality + 1))
        bee.setIcon(self:find("icon", item), propCfg.icon)
        bee.setText(self:find("count", item), _N(rewards[index].num))
        bee.addClick(item, function ()
            Game:playSound("ui_button_confirm")
            UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(rewards[index].item_id, true), target = item})
        end)
    end

    self:setButtons()

    bee.addClick(self.ClaimButton, function ()
        Game:playSound("ui_button_confirm")
        ActivityModel:getQuestionRewards(self.questionData.id)
    end)
    bee.addClick(self.EnterButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("ActivityRetentionSurveyDetails")
        bee.logEvent("Survey-click")
    end)
end

function P:evt_getQuestionRewardCallback()
    self:setButtons()
end

function P:setButtons()
    self.ClaimedButton:SetActive(self.questionData.status == 2)
    self.ClaimButton:SetActive(self.questionData.status == 1)
    self.EnterButton:SetActive(self.questionData.status == 0)
end

return P