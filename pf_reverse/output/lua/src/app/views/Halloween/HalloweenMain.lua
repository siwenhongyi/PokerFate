local P = class("HalloweenMain", require("app.views.Halloween.HalloweenBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.TaskButton = self:find("TaskButton", self.LeftBottom)
    self.ShopButton = self:find("ShopButton", self.LeftBottom)
    self.GachaButton = self:find("GachaButton", self.LeftBottom)
    -- self.StoryButton = self:find("StoryButton", self.LeftBottom)
    self.GiftButton = self:find("PackageButton", self.RightBottom)
    self.GameButton = self:find("GameButton", self.RightBottom)

    bee.addClick(self.TaskButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-task", ActivityId.Halloween)
        UiManager:showUI("HalloweenTask")
    end)

    bee.addClick(self.ShopButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-shop", ActivityId.Halloween)
        UiManager:showUI("HalloweenShop")
    end)

    -- bee.addClick(self.StoryButton, function()
    --     Game:playSound("ui_button_confirm")
    --     bee.logEvent("activity-theme-plot", ActivityId.Halloween)
    --     UiManager:showUI("HalloweenStory")
    -- end)

    bee.addClick(self.GachaButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-pool", ActivityId.Halloween)
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        ItemModel:jumpView(2006)
    end)

    bee.addClick(self.GiftButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("HalloweenPackage")
        bee.logEvent("activity-theme-gifts", ActivityId.Halloween)
    end)

    bee.addClick(self.GameButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("HalloweenJokerMain")
        bee.logEvent("joker-entrance")
    end)

    RedManager:bind(self:find("TaskButton/Reddot", self.LeftBottom), RedTag.HalloweenTask)
    -- RedManager:bind(self:find("StoryButton/Reddot", self.RightBottom), RedTag.HalloweenPlot)

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.ThemeActivity)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[102305], false)
    -- bee.invoke(self.CharacterImage, "setImageEnable", false)
    
    -- bee.logEvent("galaseason-main")

    -- local lan = LanguageManager:getLanguage()
    -- local titleRoot = self:find("Title", self.LeftTop)
    -- local count = titleRoot.transform.childCount
    -- for i = 1, count do
    --     local titleItem = titleRoot.transform:GetChild(i - 1)
    --     titleItem.gameObject:SetActive(titleItem.name == lan)
    -- end
end


return P