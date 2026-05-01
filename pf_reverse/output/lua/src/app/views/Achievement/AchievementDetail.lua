local P = class("AchievementDetail", require("app.views.Achievement.AchievementBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.selectState = {
        All = 1,
        Own = 2,
        NotOwn = 3,
    }
    self.curSelectState = self.selectState.All
    self.filterState = {
        Def = 1,
        CT = 2,
        Lv = 3,
    }
    self.curFilterState = self.filterState.Def
    self.filterStrDic = {
        [self.filterState.Def] = _T("LAB_SKIN_1001_1"),
        [self.filterState.CT] = _T("TAB_ACHIEVEMENT_4"),
        [self.filterState.Lv] = _T("TAB_ACHIEVEMENT_5"),
    }
    self.sortState = {
        Up = 1,
        Down = 2,
    }
    self.curSortState = self.sortState.Up
    self.rewardProSize = 724

    self.ThemeScroll = self:find("AchievementDetailTheme/ThemeList", self.Center)
    self.ThemeItem = self:find("Item01", self.ThemeScroll)
    self.ThemeItem:SetActive(false)

    self.ContentScrollRoot1 = self:find("AchievementDetailTask/Task01", self.Center)
    self.ContentScrollRoot2 = self:find("AchievementDetailTask/Task02", self.Center)
    self.ContentScroll1 = self:find("Ani_root/ScrollView", self.ContentScrollRoot1)
    self.ContentScroll2 = self:find("Ani_root/ScrollView", self.ContentScrollRoot2)
    self.ContentItem = self:find("AchievementDetailTask/Item01", self.Center)
    self.ContentItem:SetActive(false)

    self.ToggleGroup = self:find("Tab", self.Center)
    self.StateToggleAll = self:find("Tab1Toggle", self.ToggleGroup)
    self.StateToggleOwn = self:find("Tab2Toggle", self.ToggleGroup)
    self.StateToggleNotOwn = self:find("Tab3Toggle", self.ToggleGroup)

    self.SortButton = self:find("SortButton", self.Center)
    self.SortDown = self:find("achievement_detail_button_sort_01", self.SortButton)
    self.SortUp = self:find("achievement_detail_button_sort_02", self.SortButton)
    self.SortDown:SetActive(false)

    local filter = self:find("Filter", self.Center)
    self.FilterButton = self:find("friendroom_panel_black_grid_02", filter)
    self.FilterText = self:find("friendroom_panel_black_grid_02/TEXT", filter)
    self.ArrowTran = self:find("common_panel_black_filter_arrow/arrow", filter).transform
    self.DropDown = self:find("AnimRoot/DropDown")
    self.DropDownRoot = self:find("AnimRoot/DropDown/common_panel_black_filter_list")
    self.DropDownItem = self:find("AnimRoot/DropDown/DropDownItem")
    self.FilterMaskButton = self:find("AnimRoot/FilterMask")
    bee.setText(self.FilterText, self.filterStrDic[self.curFilterState])
    self.DropDownItem:SetActive(false)
    self.dropItems = {}

    --主题Scroll
    self.ThemeList = UiListEx:create(self.ThemeScroll)
    self.ThemeList:setTopBottom(5, 5)
    self.ThemeList:setWidth(155)
    self.ThemeList:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.ThemeItem)
    end)
    self.ThemeList:setRefreshFunc(function(data, item, isInit, index)
        self:refreshThemeItem(data, item, isInit, index)
    end)

    --内容Scroll1
    self.ContentList1 = UiListEx:create(self.ContentScroll1)
    self.ContentList1:setWidth(205)
    self.ContentList1:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.ContentItem)
    end)
    self.ContentList1:setRefreshFunc(function(data, item, isInit, index)
        self:refreshContentItem(data, item, isInit, index)
    end)
    --内容Scroll2
    self.ContentList2 = UiListEx:create(self.ContentScroll2)
    self.ContentList2:setWidth(205)
    self.ContentList2:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.ContentItem)
    end)
    self.ContentList2:setRefreshFunc(function(data, item, isInit, index)
        self:refreshContentItem(data, item, isInit, index)
    end)
    self.contags = {}

    --状态切换Toggle
    bee.onCheck(self.StateToggleAll, function(isOn) self:changeState(isOn, self.selectState.All) end)
    bee.onCheck(self.StateToggleOwn, function(isOn) self:changeState(isOn, self.selectState.Own) end)
    bee.onCheck(self.StateToggleNotOwn, function(isOn) self:changeState(isOn, self.selectState.NotOwn) end)

    --高低排序
    bee.addClick(self.SortButton, function() self:sortEvent() end)

    --筛选
    bee.addClick(self.FilterMaskButton, function() self:switchDropDown(false) end)

end

function P:onShow()
    self:InitDropDown()
    AchievementModel:refreshClearAchievement()

    self.curThemeType = self._params and self._params.themeType
    local datas = self._params and self._params.datas
    self.themeDatas = {}
    for _,v in pairs(datas) do
        table.insert(self.themeDatas, {data = v, isOn = v.id == self.curThemeType})
    end
    self.ThemeList:setDatas(self.themeDatas)
    self:refreshContent()
end

function P:hideUI()
    AchievementModel:celearThemeNewTag(self.curThemeType)
    P.super.hideUI(self)
end

--刷新主题
function P:refreshThemeItem(data, item, isInit, index)
    local itemOn = self:find("ItemOn", item)
    local itemOnTitle = self:find("Text/TEXT", itemOn)
    local itemOnValue = self:find("Text/Value", itemOn)
    local itemOnIcon = self:find("achievement_detail_theme_icon_01_on", itemOn)
    local itemOff = self:find("ItemOff", item)
    local itemOffTitle = self:find("Text/TEXT", itemOff)
    local itemOffValue = self:find("Text/Value", itemOff)
    local itemOffIcon = self:find("achievement_detail_theme_icon_01_off", itemOff)
    local reddot = self:find("reddot", item)
    reddot:SetActive(RedManager:isTag(AchievementModel.reddotLink[data.data.id]))

    bee.addClick(item, function()
        Game:playSound("ui_tab_switch_1")
        if self.curThemeType == data.data.id then
            return
        end

        AchievementModel:celearThemeNewTag(self.curThemeType)
        self.curThemeType = data.data.id
        for _,v in pairs(self.themeDatas) do
            v.isOn = data.data.id == v.data.id
        end
        self.ThemeList:refreshShowingUi()
        self:refreshContent()
    end, true)

    local cfg = tpl_achievement_theme[data.data.id]
    local hideProgress = cfg.hide_progress == 1
    itemOnValue:SetActive(not hideProgress)
    itemOffValue:SetActive(not hideProgress)
    local titlePos = bee.v3(-56.5, hideProgress and 0 or 18, 0)
    itemOnTitle.transform.localPosition = titlePos
    itemOffTitle.transform.localPosition = titlePos
    bee.setIcon(itemOnIcon, cfg.icon)
    bee.setIcon(itemOffIcon, cfg.icon)
    local titleName = _T(data.data.name)
    bee.setText(itemOnTitle, titleName)
    bee.setText(itemOffTitle, titleName)
    local progress = self:getProgress(data.data.id) .. "%"
    bee.setText(itemOnValue, progress)
    bee.setText(itemOffValue, progress)
    itemOn:SetActive(data.isOn)
    itemOff:SetActive(not data.isOn)
end

--刷新成就内容
function P:refreshContent()
    AchievementModel:arrangeData(self.curThemeType)
    for _,v in pairs(self.contags) do
        scheduler:removeTag(v)
    end
    self.contags = {}

    local cfg = tpl_achievement_theme[self.curThemeType]
    local achs = {}
    local achList = AchievementModel.achDic[self.curThemeType]
    for _,v in pairs(achList) do
        if self.curSelectState == self.selectState.Own and v.data.status >= 2 then
            table.insert(achs, v)
        elseif self.curSelectState == self.selectState.NotOwn and v.data.status < 2 then
            table.insert(achs, v)
        elseif self.curSelectState == self.selectState.All then
            table.insert(achs, v)
        end
    end
    if self.curFilterState == self.filterState.Def then
        table.sort(achs, function (a, b)
            return self:sortStep(a, b, function(aa, bb)
                return self:sortDef(aa, bb)
            end)
        end)
    elseif self.curFilterState == self.filterState.CT then
        table.sort(achs, function (a, b)
            return self:sortStep(a, b, function(aa, bb)
                return self:sortCT(aa, bb)
            end)
        end)
    elseif self.curFilterState == self.filterState.Lv then
        table.sort(achs, function (a, b)
            return self:sortStep(a, b, function (aa, bb)
                return self:sortLv(aa, bb)
            end)
        end)
    end
    
    local hasRewards = cfg.rewards ~= nil
    self.ContentScrollRoot1:SetActive(hasRewards)
    self.ContentScrollRoot2:SetActive(not hasRewards)
    local scrollRoot
    if hasRewards then
        scrollRoot = self.ContentScrollRoot1
        local rewardRoot = self:find("Ani_root/DesignationReward", self.ContentScrollRoot1)
        local rewardItem = self:find("PropItem", rewardRoot)
        PropItem:create(rewardItem, {item_id = cfg.rewards[1], num = cfg.rewards[2]})
        bee.addClick(rewardItem, function ()
            UiManager:showUI("CommonItemTip", {data = {item_id = cfg.rewards[1]}, target = rewardItem})
        end, true)
        local progress = self:getProgress(self.curThemeType)
        local progressText = self:find("Information/Value", rewardRoot)
        local progressImage = self:find("Information/ScheduleSlider/achievement_detail_designation_slider_fg", rewardRoot):GetComponent("RectTransform")
        bee.setText(progressText, progress .. "%")
        progressImage.sizeDelta = bee.v2(self.rewardProSize * progress * 0.01, progressImage.sizeDelta.y)
        local themeDone = self:find("State/Done", rewardRoot)
        local themeReceiveButton = self:find("State/ReceiveButton", rewardRoot)
        local themeInProgress = self:find("State/InProgress", rewardRoot)
        if progress >= 100 then
            if table.keyof(AchievementModel.getedRewardIds, self.curThemeType) == nil then
                themeDone:SetActive(false)
                themeReceiveButton:SetActive(true)
                bee.addClick(themeReceiveButton, function ()
                    AchievementModel:getThemeRewared(self.curThemeType)
                end, true)
            else
                themeDone:SetActive(true)
                themeReceiveButton:SetActive(false)
            end
            themeInProgress:SetActive(false)
        else
            themeDone:SetActive(false)
            themeReceiveButton:SetActive(false)
            themeInProgress:SetActive(true)
        end

        -- self.ContentList1:clear()
        self.ContentList1:switchScrollInertia(false)
        self.ContentList1:moveToYItem(1, false)
        self.ContentList1:setDatas(achs)
        self.ContentList1:switchScrollInertia(true)
    else
        scrollRoot = self.ContentScrollRoot2

        -- self.ContentList2:clear()
        self.ContentList2:switchScrollInertia(false)
        self.ContentList2:moveToYItem(1, false)
        self.ContentList2:setDatas(achs)
        self.ContentList2:switchScrollInertia(true)
    end

    local emptyDatas = table.nums(achs) == 0
    local emptyObj = self:find("Empty", scrollRoot)
    emptyObj:SetActive(emptyDatas)
    self:find("TaskScrollbar", scrollRoot):GetComponent("CanvasGroup").alpha = emptyDatas and 0 or 1
    local strId = ""
    if self.curSelectState == self.selectState.Own then
        strId = "LAB_LEADERBOARD_11"
    elseif self.curSelectState == self.selectState.NotOwn then
        strId = "TAB_ACHIEVEMENT_12"
    end
    local emptyTextObj = self:find("TEXT", emptyObj)
    bee.setText(emptyTextObj, _T(strId))
end
----排序
function P:sortStep(a, b, action)
    local raa, rbb = self:sortRewardItem(a, b)
    if raa ~= rbb then
        return raa
    else
        local naa = self:isNewAchievement(self.curThemeType, a.cfg.id)
        local nbb = self:isNewAchievement(self.curThemeType, b.cfg.id)
        if naa ~= nbb then
            return naa
        else
            return action(a, b)
        end
    end
end
function P:sortDef(a, b)
    if self.curSortState == self.sortState.Up then
        return a.cfg.id < b.cfg.id
    else
        return a.cfg.id > b.cfg.id
    end
end
function P:sortCT(a, b)
    if self.curSortState == self.sortState.Up then
        if a.data.status >= 2 and b.data.status >= 2 then
            if a.data.updated_at == b.data.updated_at then
                return a.cfg.id < b.cfg.id
            else
                return a.data.updated_at > b.data.updated_at
            end
        elseif a.data.status == 1 and b.data.status == 1 then
            return a.cfg.id < b.cfg.id
        else
            return a.data.status > b.data.status
        end
    else
        if a.data.status >= 2 and b.data.status >= 2 then
            if a.data.updated_at == b.data.updated_at then
                return a.cfg.id > b.cfg.id
            else
                return a.data.updated_at < b.data.updated_at
            end
        elseif a.data.status == 1 and b.data.status == 1 then
            return a.cfg.id > b.cfg.id
        else
            return a.data.status > b.data.status
        end
    end
end
function P:sortLv(a, b)
    if a.cfg.ach_level == b.cfg.ach_level then
        if self.curSortState == self.sortState.Up then
            return a.cfg.id < b.cfg.id
        else
            return a.cfg.id > b.cfg.id
        end
    else
        if self.curSortState == self.sortState.Up then
            return a.cfg.ach_level < b.cfg.ach_level
        else
            return a.cfg.ach_level > b.cfg.ach_level
        end
    end
end
function P:sortRewardItem(a, b)
    local aa = a.cfg.rewards ~= nil and #a.cfg.rewards > 0 and a.data.status == 2
    local bb = b.cfg.rewards ~= nil and #b.cfg.rewards > 0 and b.data.status == 2
    return aa, bb
end

--刷新具体成就
function P:refreshContentItem(data, item, isInit, index)
    local cfg = data.cfg
    local d = data.data

    local Ani_root = self:find("Ani_root", item)
    if isInit then
        local tag = self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_TaskView_item_into", Ani_root)
        end)
        table.insert(self.contags, tag)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_TaskView_item_idle", Ani_root)
    end

    local lvIcon = self:find("Ani_root/Icon", item)
    local name = self:find("Ani_root/Information/Name", item)
    local sline = self:find("Ani_root/Information/Describe/SingleLine", item)
    local tline = self:find("Ani_root/Information/Describe/TwoLines", item)
    local reward = self:find("Ani_root/TaskReward", item)
    local newTip = self:find("Ani_root/common_result_tag_new", item)

    --等级
    bee.setIcon(lvIcon, string.format("achievement_level_%s", cfg.ach_level), "Achievement", true)

    --所需条件值
    local needValue, gameStr = AchievementModel:getDesValue(cfg)

    --描述
    bee.setText(name, _T(cfg.name))
    local desStr = _F(cfg.des, _N(needValue), gameStr)
    if cfg.task_type == 204 then
        local nameStr = _T(tpl_character[cfg.value[1]].name)
        desStr = _F(cfg.des, nameStr)
    end
    local sdes = self:find("Des", sline)
    sline:SetActive(true)
    tline:SetActive(false)
    bee.setText(sdes, desStr)
    local clearRate = AchievementModel:getAllServerProgress(d.rate, d.finish)
    if sdes:GetComponent("Text").preferredWidth > sdes:GetComponent("RectTransform").sizeDelta.x then
        sline:SetActive(false)
        tline:SetActive(true)
        bee.setText(self:find("Des", tline), desStr)
        bee.setText(self:find("Tip", tline), _F("TAB_ACHIEVEMENT_8", clearRate))
    else
        bee.setText(self:find("Tip", sline), _F("TAB_ACHIEVEMENT_8", clearRate))
    end

    --奖励
    if cfg.rewards ~= nil and next(cfg.rewards) ~= nil then
        reward:SetActive(true)
        local rewardTran = self:find("Ani_root/TaskReward", item)
        local rewardItem = self:find("PropItem", rewardTran)
        PropItem:create(rewardItem, {item_id = cfg.rewards[1], num = cfg.rewards[2]})
        local received = self:find("Received", rewardTran)
        local eff = self:find("Effect", rewardTran)
        eff:SetActive(d.status == 2)
        received:SetActive(d.status == 3)
        bee.addClick(rewardItem, function ()
            if d.status == 1 then
                UiManager:showUI("CommonItemTip", {data = {item_id = cfg.rewards[1]}, target = rewardItem})
            elseif d.status == 2 then
                AchievementModel:getAchievementReward(self.curThemeType, cfg.id)
            end
        end, true)

        -- local ani = self:find("Ani_root", item):GetComponent("Animator")
        -- ani.enabled = isInit
    else
        reward:SetActive(false)
    end

    --进度
    local schedule = self:find("Ani_root/State/Schedule", item)
    local completed = self:find("Ani_root/State/Completed", item)
    if d.status == 1 then
        schedule:SetActive(true)
        completed:SetActive(false)
        local progress = self:find("Value", schedule)
        bee.setText(progress, string.format("<color=#FFDBA3>%s</color>/%s", _N(d.current_value), _N(needValue)))
    else
        schedule:SetActive(false)
        completed:SetActive(true)
        local time = self:find("Time", completed)
        local timeDate = TimeHelp:getDateStr(d.updated_at, "/")
        bee.setText(time, timeDate)
    end

    --新完成标志
    -- local newList = AchievementModel.newTagDic[self.curThemeType].newList
    -- local isNew = table.keyof(newList, cfg.id) ~= nil
    local isNew = self:isNewAchievement(self.curThemeType, cfg.id)
    newTip:SetActive(isNew)
end

--是否为新达成成就
function P:isNewAchievement(themeId, achId)
    local newList = AchievementModel.newTagDic[themeId].newList
    return table.keyof(newList, achId) ~= nil
end

--状态切换
function P:changeState(isOn, state)
    if not isOn then
        return
    end
    if self.curSelectState == state then
        return
    end

    self.curSelectState = state
    self:refreshContent()
end

--高低排序
function P:sortEvent()
    self.curSortState = self.curSortState == self.sortState.Up and self.sortState.Down or self.sortState.Up
    self.SortDown:SetActive(self.curSortState == self.sortState.Down)
    self.SortUp:SetActive(self.curSortState == self.sortState.Up)
    self:refreshContent()
end

--筛选
function P:InitDropDown()
    local count = table.nums(self.filterState)
    for i = 1, count do
        local item = {}
        local itemGo = CU.GameObject.Instantiate(self.DropDownItem, self.DropDownRoot.transform, false)
        itemGo:SetActive(true)
        item.type = i
        item.go = itemGo
        item.on = bee.find("On", itemGo)
        item.off = bee.find("Off", itemGo)
        local str = self.filterStrDic[i]
        bee.setText(bee.find("On/TEXT", itemGo), str)
        bee.setText(bee.find("Off/TEXT", itemGo), str)
        bee.addClick(itemGo, function()
            if self.curFilterState == i then
                self:switchDropDown(false)
                return
            end
            self.curFilterState = i
            bee.setText(self.FilterText, str)
            self:refreshContent()
            self:switchDropDown(false)
        end)
        table.insert(self.dropItems, item)
    end

    bee.addClick(self.FilterButton, function()
        self:switchDropDown(true)
    end)

    local dropDownTran = self.DropDownRoot:GetComponent("RectTransform")
    dropDownTran.sizeDelta = bee.v2(dropDownTran.sizeDelta.x, (50 + 10) * count + 40)
end
function P:switchDropDown(sw)
    self.FilterMaskButton:SetActive(sw)
    self.DropDown:SetActive(sw)
    self.ArrowTran.localEulerAngles = bee.v3(0, 0, sw and 0 or 180)

    if sw then
        for _,v in pairs(self.dropItems) do
            v.on:SetActive(v.type == self.curFilterState)
            v.off:SetActive(v.type ~= self.curFilterState)
        end
    end
end

function P:evt_refreshThemeReward(themeId)
    if themeId ~= self.curThemeType then
        return
    end
    local cfg = tpl_achievement_theme[self.curThemeType]
    if cfg.rewards == nil then
        return
    end

    local rewardRoot = self:find("Ani_root/DesignationReward", self.ContentScrollRoot1)
    local themeDone = self:find("State/Done", rewardRoot)
    local themeReceiveButton = self:find("State/ReceiveButton", rewardRoot)
    themeDone:SetActive(true)
    themeReceiveButton:SetActive(false)
end

function P:evt_refreshAchievementReward(msg)
    if msg.themeId ~= self.curThemeType then
        return
    end
    self:refreshContent()
    -- local cfg = tpl_achievement_theme[self.curThemeType]
    -- local contentList = cfg.rewards == nil and self.ContentList2 or self.ContentList1
    -- local items = contentList:getDatas()
    -- for _,v in pairs(items) do
    --     if v.data.data.task_id == msg.achId then
    --         if not bee.isNull(v.node) then
    --             local rewardTran = self:find("Ani_root/TaskReward", v.node)
    --             local eff = self:find("Effect", rewardTran)
    --             local received = self:find("Received", rewardTran)
    --             eff:SetActive(false)
    --             received:SetActive(true)
    --         end
    --     end
    -- end
end

--刷新主题红点
function P:evt_refreshAchievementThemeReddot(themeId)
    local items = self.ThemeList:getDatas()
    for _,v in pairs(items) do
        if v.data.data.id == themeId then
            local reddot = self:find("reddot", v.node)
            reddot:SetActive(RedManager:isTag(AchievementModel.reddotLink[themeId]))
        end
    end
end

return P