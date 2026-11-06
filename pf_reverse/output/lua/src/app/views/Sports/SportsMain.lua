local P = class("SportsMain", require("app.views.Sports.SportsBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.titles = self:find("Title", self.RightTop)

    self.TaskButton = self:find("TaskButton", self.LeftBottom)
    self.ShopButton = self:find("ShopButton", self.LeftBottom)
    self.GiftButton = self:find("GiftButton", self.LeftBottom)
    self.StoryButton = self:find("StoryButton", self.RightBottom)
    self.GachaButton = self:find("GachaButton", self.RightBottom)

    bee.addClick(self.TaskButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-task", ActivityId.Sports)
        UiManager:showUI("SportsTask")
    end)

    bee.addClick(self.ShopButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-shop", ActivityId.Sports)
        UiManager:showUI("SportsShop")
    end)

    bee.addClick(self.StoryButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-plot", ActivityId.Sports)
        UiManager:showUI("SportsStory")
    end)

    bee.addClick(self.GachaButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-pool", ActivityId.Sports)
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        ItemModel:jumpView(2006)
    end)

    bee.addClick(self.GiftButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SportsPackage")
    end)

    local taskReddot = self:find("TaskButton/Reddot", self.LeftBottom).transform
    local taskReddotPos = 0
    taskReddotPos =  LanguageManager:getLanguage() == "en" and -91.5 or -65
    taskReddot.localPosition = bee.v3(taskReddotPos, taskReddot.localPosition.y, 0)


    RedManager:bind(self:find("TaskButton/Reddot", self.LeftBottom), RedTag.SportsTask)
    RedManager:bind(self:find("StoryButton/Reddot", self.RightBottom), RedTag.SportsPlot)

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.ThemeActivity)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[101505], false)
    -- bee.logEvent("galaseason-main")

    local count = self.titles.transform.childCount
    local lan = LanguageManager:getLanguage()
    for i = 1, count do
        local obj = self.titles.transform:GetChild(i - 1)
        obj.gameObject:SetActive(obj.name == "title_" .. lan)
    end
end


return P