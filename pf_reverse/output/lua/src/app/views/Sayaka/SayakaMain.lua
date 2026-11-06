local P = class("SayakaMain", require("app.views.Sayaka.SayakaBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.TaskButton = self:find("TaskButton", self.RightBottom)
    self.ShopButton = self:find("ShopButton", self.RightBottom)
    self.GiftButton = self:find("GiftButton", self.LeftBottom)
    self.StoryButton = self:find("StoryButton", self.LeftBottom)
    self.GachaButton = self:find("GachaButton", self.RightBottom)

    bee.addClick(self.TaskButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-task", ActivityId.Sayaka)
        UiManager:showUI("SayakaTask")
    end)

    bee.addClick(self.ShopButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-shop", ActivityId.Sayaka)
        UiManager:showUI("SayakaShop")
    end)

    bee.addClick(self.StoryButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-plot", ActivityId.Sayaka)
        UiManager:showUI("SayakaStory")
    end)

    bee.addClick(self.GachaButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-pool", ActivityId.Sayaka)
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        ItemModel:jumpView(2007)
    end)

    bee.addClick(self.GiftButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SayakaPackage")
    end)

    RedManager:bind(self:find("TaskButton/Reddot", self.RightBottom), RedTag.SayakaTask)
    RedManager:bind(self:find("StoryButton/Reddot", self.LeftBottom), RedTag.SayakaPlot)

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.ThemeActivity)
end

function P:onShow()
    P.super.onShow(self)
    -- bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[101505], false)
    -- bee.logEvent("galaseason-main")

    -- local count = 4
    local lan = LanguageManager:getLanguage()
    local titles = self:find("Bottom/Title/title", self.AnimRoot)
    local titleName = "sayaka_main_title_" .. lan
    local giftTitles = self:find("title", self.GiftButton)
    local giftTitleName = "sayaka_main_button_gift_" ..lan
    local storyTitles = self:find("title", self.StoryButton)
    local storyTitleName = "sayaka_main_button_story_" ..lan
    local taskTitles = self:find("title", self.TaskButton)
    local taskTitleName = "sayaka_main_button_task_" ..lan
    local shopTitles = self:find("title", self.ShopButton)
    local shopTitleName = "sayaka_main_button_shop_" ..lan
    local gachaTitles = self:find("title", self.GachaButton)
    local gachaTitleName = "sayaka_main_gacha_" ..lan
    for i = 1, 4 do
        local titleObj = titles.transform:GetChild(i - 1)
        titleObj.gameObject:SetActive(titleObj.name == titleName)
        local giftObj = giftTitles.transform:GetChild(i - 1)
        giftObj.gameObject:SetActive(giftObj.name == giftTitleName)
        local storyObj = storyTitles.transform:GetChild(i - 1)
        storyObj.gameObject:SetActive(storyObj.name == storyTitleName)
        local taskObj = taskTitles.transform:GetChild(i - 1)
        taskObj.gameObject:SetActive(taskObj.name == taskTitleName)
        local shopObj = shopTitles.transform:GetChild(i - 1)
        shopObj.gameObject:SetActive(shopObj.name == shopTitleName)
        local gachaObj = gachaTitles.transform:GetChild(i - 1)
        gachaObj.gameObject:SetActive(gachaObj.name == gachaTitleName)
    end
end


return P