local P = class("AchievementMain", require("app.views.Achievement.AchievementBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.ReGuideButton = self:find("ReGuideButton", self.LeftTop)
    self.ScrollView = self:find("AchievementTheme/ScrollView", self.Center)
    self.ScrollRect = self.ScrollView:GetComponent("ScrollRect")
    self.Item = self:find("AchievementTheme/Item01", self.Center)
    self.Item:SetActive(false)
    self.proDefWidth = 272

    self.Loading = self:find("AnimRoot/Loading")

    bee.addClick(self:find("RecordButton", self.LeftBottom), function ()
        bee.logEvent("achievement-get")
        Game:playSound("ui_button_confirm")
        UiManager:showUI("AchievementRecord")
        -- self:()
    end)
    bee.addClick(self.ReGuideButton, function ()
        Game:playSound("ui_button_confirm")
        self:reGuide()
    end)

    self.themeDatas = {}
    self.ListAchievement = UiListEx:create(self.ScrollView)
    self.ListAchievement:setWidth(420)
    self.ListAchievement:setTopBottom(100, 100)
    self.ListAchievement:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.ListAchievement:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)

    self.guiding = false
    self.firstReddot = 0

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.Achievement)
end

function P:onShow()
    self.LeftBottom:SetActive(false)
    self.RightTop:SetActive(false)
    self.Loading:SetActive(true)
    AchievementModel:requestAchTaskClearCount()
    AchievementModel:requestAchTaskList()
end

function P:evt_refreshAchievement()
    self:initThemeItem()
    AchievementModel:refreshClearAchievement()
    self.LeftBottom:SetActive(true)
    self.RightTop:SetActive(true)
    self.Loading:SetActive(false)
    self:anchievementGuide()
    self:checkJumpToClearTheme()
end

function P:initThemeItem()
    for _,v in pairs(tpl_achievement_theme) do
        table.insert(self.themeDatas, v)
    end
    table.sort(self.themeDatas, function(a, b) return a.order < b.order end)
    self.ListAchievement:setDatas(self.themeDatas)
end

function P:checkJumpToClearTheme()
    if self.guiding then
        return
    end
    if self.firstReddot > 0 then
        self.ListAchievement:moveToYItem(self.firstReddot, false, -100)
    end
end

function P:refreshItem(data, item, isInit, index)
    --item:SetActive(true)
    local aniRoot = self:find("Ani_root", item)
    local type1 = self:find("Type1", aniRoot)
    local progress = self:find("ScheduleSlider/achievement_main_theme_slider_fg", type1)
    local progressTran = progress:GetComponent("RectTransform")
    local progressValue = self:find("Progress", type1)
    local name1 = self:find("TEXT", type1)
    local type2 = self:find("Type2", aniRoot)
    local name2 = self:find("TEXT", type2)
    local icon = self:find("achievement_main_theme_icon_01", aniRoot)
    local reddot = self:find("common_reddot_01", aniRoot)
    local dot = RedManager:isTag(AchievementModel.reddotLink[data.id])
    reddot:SetActive(dot)
    if dot then
        if self.firstReddot == 0 then
            self.firstReddot = index
        end
    end

     if isInit then
        self:once(0.1 * (index - 1), function()
            item:SetActive(true)
            self:playAnimator("UI_1_AchievementMain_item", aniRoot)
        end)
        item:SetActive(false)
    else
        item:SetActive(true)
        self:playAnimator("UI_1_AchievementMain_item_idle", aniRoot)
    end

    if not data.hide_progress then
        type1:SetActive(true)
        type2:SetActive(false)
        local progress = self:getProgress(data.id)
        progressTran.sizeDelta = bee.v2(self.proDefWidth * progress * 0.01, progressTran.sizeDelta.y)
        bee.setText(progressValue, tostring(progress) .. "%")
        bee.setText(name1, _T(data.name))
    else
        type1:SetActive(false)
        type2:SetActive(true)
        bee.setText(name2, _T(data.name))
    end

    bee.setIcon(icon, data.icon)
    bee.addClick(item, function()
        bee.logEvent("achievement-theme", data.id)
        UiManager:showUI("AchievementDetail", {themeType = data.id, datas = self.themeDatas})
    end, true)
end

--刷新主题红点
function P:evt_refreshAchievementThemeReddot(themeId)
    local items = self.ListAchievement:getDatas()
    for _,v in pairs(items) do
        if v.data.id == themeId then
            local reddot = self:find("Ani_root/common_reddot_01", v.node)
            reddot:SetActive(RedManager:isTag(AchievementModel.reddotLink[themeId]))
        end
    end
end

function P:hideUI()
    P.super.hideUI(self)
    self.Loading:SetActive(false)
end

--引导
function P:anchievementGuide()
	self.guiding = GuideManager:startSystemGuide(16001, 0.65)
end

function P:reGuide()
    self.ListAchievement:moveToYItem(1, false)
    GuideManager:startSystemGuide(16001, 0, true)
end

return P