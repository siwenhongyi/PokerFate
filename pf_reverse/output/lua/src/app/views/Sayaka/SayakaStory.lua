local P = class("SayakaStory", require("app.views.Sayaka.SayakaBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.Entrance = self:find("Entrance", self.Center)
    self.Items = {
        self:find("Item1", self.Entrance),
        self:find("Item2", self.Entrance),
        self:find("Item3", self.Entrance),
        self:find("Item4", self.Entrance),
    }

    self.storyList = {}
end

function P:onShow()
    P.super.onShow(self)
    self:find("RoleSpine/Role3001_6/Image", self.CharacterImage):SetActive(true)
    self:find("RoleSpine/Role3001_6/ImageFg", self.CharacterImage):SetActive(true)
    -- bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[300106], true)

    local data = tpl_theme_activity[ThemeModel:getConfId()]
    self.storyList = get_tpl_subKey(tpl_theme_storys_list, "group", data.storys)
    table.sort(self.storyList, function(a, b) return a.unlock_time < b.unlock_time end)
    local count = table.nums(self.storyList)
    for i = 1, count do
        self:refreshItem(self.storyList[i], self.Items[i], true, i)
    end
end

function P:refreshItem(data, item, isInit, index)
    local Ani_root = self:find("Ani_root", item)
    Ani_root = item
    -- if isInit then
    --     self:once(0.1 * (index - 1), function()
    --         Ani_root:SetActive(true)
    --         self:playAnimator("UI_2_HotSpringPlot_PiyoList", Ani_root)
    --     end)
    --     Ani_root:SetActive(false)
    -- else
    --     Ani_root:SetActive(true)
    --     self:playAnimator("UI_2_HotSpringPlot_PiyoList_idle", Ani_root)
    -- end
    local frameA = self:find("sayaka_story_frame_a_01", Ani_root)
    local frameB = self:find("sayaka_story_frame_b_01", Ani_root)
    local rewardItem = self:find("sayaka_story_frame_ice_01", Ani_root)
    local rewardLock = self:find("sayaka_story_frame_ice_02", Ani_root)
    local rewardGeted = self:find("sayaka_story_frame_ice_mask", Ani_root)
    local dayFrameA = self:find("sayaka_story_frame_time_a", Ani_root)
    local dayFrameB = self:find("sayaka_story_frame_time_b", Ani_root)
    local dayText = self:find("day", Ani_root)
    local dayValue = self:find("DayValue", Ani_root)
    local dayValue2 = self:find("DayValue2", Ani_root)
    local title = self:find("Text", Ani_root)
    local propIcon = self:find("icon_activity_s6_01", Ani_root)
    local propCount = self:find("ItemCount", Ani_root)

    frameA:SetActive(false)
    frameB:SetActive(false)
    dayFrameA:SetActive(false)
    dayFrameB:SetActive(false)
    rewardItem:SetActive(false)
    rewardLock:SetActive(false)
    rewardGeted:SetActive(false)
    dayValue:SetActive(false)
    dayValue2:SetActive(false)

    -- local day = string.format("%02d", data.unlock_time + 1)
    -- dayValue.transform:GetComponent("Text").text = day
    -- dayValue2.transform:GetComponent("Text").text = day
    bee.setText(title, _T(data.name))
    local dayLock = data.unlock_time > ThemeModel:getOpenDay()
    local chapterLock = self:_isLockPlod(data)
    bee.setIcon(propIcon, tpl_props[data.rewards[1]].icon)
    -- local mask = dayLock or chapterLock
    if not (dayLock or chapterLock) then
        frameA:SetActive(true)
        dayFrameA:SetActive(true)
        dayValue:SetActive(true)
        bee.setColor(dayText, bee.colorHex("#6293EE"), "Text")
        bee.setColor(title, bee.colorHex("#2B71AD"), "Text")
        rewardItem:SetActive(true)
        bee.setText(propCount, "x" .. _N(data.rewards[2]))
        local geted = ThemeModel:isPlotRewarded(data.id)
        rewardGeted:SetActive(geted)
        propCount:SetActive(not geted)
    else
        frameB:SetActive(true)
        dayFrameB:SetActive(true)
        dayValue2:SetActive(true)
        bee.setColor(dayText, bee.colorHex("#4467A6"), "Text")
        bee.setColor(title, bee.colorHex("#1E4F79"), "Text")
        propCount:SetActive(false)
        -- if dayLock then
        --     bee.setText(title, _T(""))
        -- elseif chapterLock then
        --     bee.setText(title, _T("LAB_THEME_ACTIVITY1_TIPS_1"))
        -- end
        rewardLock:SetActive(true)
    end

    bee.addClick(propIcon, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(data.rewards[1], true), target = propIcon})
    end, true)
    bee.addClick(item, function()
        Game:playSound("ui_button_confirm")
        local day = ThemeModel:getOpenDay()
        if data.unlock_time > day then
            UiManager:showToast(_F("LAB_THEME_ACTIVITY1_TIPS_2", data.unlock_time - day))
            return
        end
        if self:_isLockPlod(data) then
            UiManager:showToast(_T("LAB_THEME_ACTIVITY1_TIPS_1"))
            return
        end
        bee.logEvent("onsen-plot_play", data.id, data.group)
        StoryModel.storyData = data
        UiManager:showUI("Story", {name = data.res, storyData = data, StoryRecord = "SayakaLog", StorySkip = "SayakaPlot", themeStory = true, hideCb = function()
            local ret = ThemeModel:reqPlotReward(data.id, function()
                self:refreshItem(data, item, false, index)
                local nextIndex = index + 1
                if nextIndex <= #self.storyList then
                    self:refreshItem(self.storyList[nextIndex], self.Items[nextIndex], false, nextIndex)
                end
            end)
            if not StoryModel.isSkip then
                -- bee.logEvent("onsen-plot_finish", data.id, data.group, ret and 1 or 0)
            end
        end})
    end, true)
    -- bee.addClick(self:find("frame_column_lock", Ani_root), function()
    --     Game:playSound("ui_button_confirm")
    --     local day = ThemeModel:getOpenDay()
    --     print("==== ggggggg day", day, data.unlock_time)
    --     if data.unlock_time > day then
    --         UiManager:showToast(_F("LAB_THEME_ACTIVITY1_TIPS_2", data.unlock_time - day))
    --         return
    --     end
    --     if self:_isUnlockPlod(data) then
    --         UiManager:showToast(_T("LAB_THEME_ACTIVITY1_TIPS_1"))
    --         return
    --     end
    -- end, true)
end

function P:_isLockPlod(data)
    local curPlotId = ThemeModel:getCurPlotId()
    if data.unlock_time > 0 then
        if curPlotId == 0 and self.storyList[1].id == data.id then
            return false
        elseif curPlotId > 0 and curPlotId >= data.id - 1 then
            return false
        end
        return true
    else
        return false
    end
    -- return data.unlock_time > 0 and curPlotId > 0 and curPlotId < data.id - 1
end

-- function P:getStoryData(item_id)
--     local data = ThemeModel:getConfData()
--     if not data then return {} end

--     local storys = get_tpl_subKey(tpl_theme_storys_list, "group", data.storys)
--     for _, v in ipairs(storys) do
--         if v.unlock_item and v.unlock_item[1] == item_id then
--             return v
--         end
--     end
--     return {}
-- end

-- function P:evt_ItemChangeRSP(msg)
--     for _, v in ipairs(msg.item_list) do
--         for kk, vv in ipairs(self.item_ids) do
--             if v.item_id == vv then
--                 self:refreshItem(self.Items[kk], vv)
--                 break
--             end
--         end
--     end
-- end

function P:hideUI()
    P.super.hideUI(self)
    if self._is_show then
		self:hideTopUI()
	end
end

return P