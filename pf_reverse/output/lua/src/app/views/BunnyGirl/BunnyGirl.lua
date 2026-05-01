local P = class("BunnyGirl", require("app.views.BunnyGirl.BunnyGirlBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.TaskButton = self:find("TaskButton", self.LeftBottom)
    self.ShopButton = self:find("ShopButton", self.LeftBottom)
    self.StoryButton = self:find("StoryButton", self.RightBottom)
    self.GachaButton = self:find("GachaButton", self.RightBottom)
    self.GiftButton = self:find("GiftButton", self.RightBottom)

    self.titles = self:find("Title/bunnygirl_title", self.LeftTop)

    bee.addClick(self.TaskButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("BunnyGirlTask")
    end)

    bee.addClick(self.ShopButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("BunnyGirlShop")
    end)

    bee.addClick(self.StoryButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("BunnyGirlStory")
    end)

    bee.addClick(self.GachaButton, function()
        Game:playSound("ui_button_confirm")
        
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        ItemModel:jumpView(2005)
    end)

    bee.addClick(self.GiftButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("BunnyGirlPackage")
    end)

    RedManager:bind(self:find("TaskButton/Reddot", self.LeftBottom), RedTag.BunnyGirlTask)
    RedManager:bind(self:find("StoryButton/Reddot", self.RightBottom), RedTag.BunnyGirlPlot)

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.ThemeActivity)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[101405], false)

    local count = self.titles.transform.childCount
    for i = 1, count do
        local obj = self.titles.transform:GetChild(i - 1)
        obj.gameObject:SetActive(obj.name == string.upper(LanguageManager:getLanguage()))
    end
    -- bee.logEvent("galaseason-main")
end


return P