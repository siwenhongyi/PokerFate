local P = class("RacingMain", require("app.views.Racing.RacingBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.TaskButton = self:find("TaskButton", self.RightBottom)
    self.ShopButton = self:find("ShopButton", self.RightBottom)
    self.GiftButton = self:find("GiftButton", self.LeftBottom)
    self.GachaButton = self:find("GachaButton", self.LeftBottom)

    bee.addClick(self.TaskButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-task", ActivityId.Racing)
        UiManager:showUI("RacingTask")
    end)

    bee.addClick(self.ShopButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-lottery", ActivityId.Racing)
        UiManager:showUI("RacingLottery")
    end)

    -- bee.addClick(self.StoryButton, function()
    --     Game:playSound("ui_button_confirm")
    --     bee.logEvent("activity-theme-plot", ActivityId.Racing)
    --     UiManager:showUI("RacingStory")
    -- end)

    bee.addClick(self.GachaButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-pool", ActivityId.Racing)
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        ItemModel:jumpView(2006)
    end)

    bee.addClick(self.GiftButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("RacingPackage")
        bee.logEvent("activity-theme-gifts", ActivityId.Racing)
        
    end)

    RedManager:bind(self:find("TaskButton/Reddot", self.RightBottom), RedTag.RacingTask)
    -- RedManager:bind(self:find("StoryButton/Reddot", self.RightBottom), RedTag.RacingPlot)

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.ThemeActivity)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[102105], false)

    local lan = LanguageManager:getLanguage()
    local taskTitleRoot = self:find("Title", self.TaskButton)
    local shopTitleRoot = self:find("Title", self.ShopButton)
    local giftTitleRoot = self:find("Title", self.GiftButton)
    local gachaTitleRoot = self:find("Title", self.GachaButton)
    local themeTitleRoot = self:find("Title/Title", self.RightBottom)

    for i = 1, 4 do
        local taskTitleItem = taskTitleRoot.transform:GetChild(i - 1)
        taskTitleItem.gameObject:SetActive(taskTitleItem.name == "racing_main_button_task_" .. lan)

        local shopTitleItem = shopTitleRoot.transform:GetChild(i - 1)
        shopTitleItem.gameObject:SetActive(shopTitleItem.name == "racing_main_button_shop_" .. lan)

        local giftTitleItem = giftTitleRoot.transform:GetChild(i - 1)
        giftTitleItem.gameObject:SetActive(giftTitleItem.name == "racing_main_button_gift_" .. lan)

        local gachaTitleItem = gachaTitleRoot.transform:GetChild(i - 1)
        gachaTitleItem.gameObject:SetActive(gachaTitleItem.name == "racing_main_button_gacha_" .. lan)

        local themeTitleItem = themeTitleRoot.transform:GetChild(i - 1)
        themeTitleItem.gameObject:SetActive(themeTitleItem.name == "racing_main_title_" .. lan)
    end
end


return P