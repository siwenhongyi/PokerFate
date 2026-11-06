local P = class("MatsuriMain", require("app.views.Matsuri.MatsuriBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.TaskButton = self:find("TaskButton", self.LeftBottom)
    self.ShopButton = self:find("ShopButton", self.LeftBottom)
    -- self.StoryButton = self:find("StoryButton", self.LeftBottom)
    self.GiftButton = self:find("GiftButton", self.RightBottom)
    self.GachaButton = self:find("GachaButton", self.RightBottom)

    bee.addClick(self.TaskButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-task", ActivityId.Matsuri)
        UiManager:showUI("MatsuriTask")
    end)

    bee.addClick(self.ShopButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-shop", ActivityId.Matsuri)
        UiManager:showUI("MatsuriShop")
    end)

    -- bee.addClick(self.StoryButton, function()
    --     Game:playSound("ui_button_confirm")
    --     bee.logEvent("activity-theme-plot", ActivityId.Matsuri)
    --     UiManager:showUI("MatsuriStory")
    -- end)

    bee.addClick(self.GachaButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-pool", ActivityId.Matsuri)
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        ItemModel:jumpView(2006)
    end)

    bee.addClick(self.GiftButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("MatsuriPackage")
        bee.logEvent("activity-theme-gifts", ActivityId.Matsuri)
        
    end)

    RedManager:bind(self:find("TaskButton/Reddot", self.LeftBottom), RedTag.MatsuriTask)
    -- RedManager:bind(self:find("StoryButton/Reddot", self.RightBottom), RedTag.MatsuriPlot)

    local speFlower = self:find("Title/matsuri_main_title_flower_01", self.LeftTop)
    local lan = LanguageManager:getLanguage()
    if lan == "en" then
        speFlower.transform:SetSiblingIndex(1)
    end

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.ThemeActivity)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100406], false)
    -- bee.logEvent("galaseason-main")

    local lan = LanguageManager:getLanguage()

    for i = 1, 4 do
        local taskTitleRoot = self:find("Title", self.TaskButton)
        local taskTitleItem = taskTitleRoot.transform:GetChild(i - 1)
        taskTitleItem.gameObject:SetActive(taskTitleItem.name == "matsuri_main_title_task_" .. lan)

        local shopTitleRoot = self:find("Title", self.ShopButton)
        local shopTitleItem = shopTitleRoot.transform:GetChild(i - 1)
        shopTitleItem.gameObject:SetActive(shopTitleItem.name == "matsuri_main_title_shop_" .. lan)

        local giftTitleRoot = self:find("Title", self.GiftButton)
        local giftTitleItem = giftTitleRoot.transform:GetChild(i - 1)
        giftTitleItem.gameObject:SetActive(giftTitleItem.name == "matsuri_main_title_pack_" .. lan)

        local gachaTitleRoot = self:find("Title", self.GachaButton)
        local gachaTitleItem = gachaTitleRoot.transform:GetChild(i - 1)
        gachaTitleItem.gameObject:SetActive(gachaTitleItem.name == "matsuri_main_title_gacha_" .. lan)
    end
end


return P