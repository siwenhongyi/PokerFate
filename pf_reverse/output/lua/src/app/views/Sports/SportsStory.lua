local P = class("SportsStory", require("app.views.Sports.SportsBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.Entrance = self:find("Entrance", self.Center)

    self.Items = {
        self:find("Item1", self.Entrance),
        self:find("Item2", self.Entrance),
        self:find("Item3", self.Entrance),
    }
    self.item_ids = ThemeModel.SportsStoryItems
end

function P:onShow()
    P.super.onShow(self)

    for k, v in ipairs(self.Items) do
        self:refreshItem(v, self.item_ids[k])
        local Icon = self:find("Item1/icon_giftpack_03_1", v)
        local storyData = self:getStoryData(self.item_ids[k])
        bee.setIcon(Icon, tpl_props[storyData.rewards[1]].icon)
        bee.addClick(Icon, function()
            Game:playSound("ui_button_confirm")
            if storyData then
                UiManager:showUI("CommonItemTip", {data = {id = storyData.rewards[1]}, target = Icon})
            end
        end)
            
    end
end

function P:refreshItem(item, item_id)
    local ImgOn = self:find("sports_story_img_character_a", item)
    local ImgOff = self:find("sports_story_img_character_b", item)
    local LockTran = self:find("Lock", item)
    local Effect = self:find("Eff_poker_Sprots_story_light", LockTran)
    local StoryIcon = self:find("sports_story_main_icon_01", LockTran)
    local LockIcon = self:find("sports_story_img_lock", LockTran)
    local StoryTip = self:find("Text", LockTran)
    local RewardTip = self:find("Item1/Completion Reward", item)
    local RewardIcon = self:find("Item1/icon_giftpack_03-1", item)
    local RewardGetedMask = self:find("Item1/sports_story_img_done", item)

    bee.setIcon(StoryIcon, tpl_props[item_id].icon)
    bee.setIcon(RewardIcon, tpl_props[item_id].icon)

    local data = ItemModel:getItem(item_id)
    if not data then
        ImgOn:SetActive(false)
        ImgOff:SetActive(true)
        LockTran:SetActive(true)
        Effect:SetActive(false)
        LockIcon:SetActive(true)
        bee.setText(StoryTip, _F("LAB_THEME_ACTIVITY5_8", _T(tpl_props[item_id].name)))
        RewardGetedMask:SetActive(false)
        bee.setText(RewardTip, _T("LAB_THEME_ACTIVITY5_12"))

        bee.addClick(item, function()
            UiManager:showUI("SportsNotice", {
                text = _F("LAB_THEME_ACTIVITY5_9", _T(tpl_props[item_id].name)),
                onSure = function()
                    UiManager:showUI("SportsShop")
                end,
            })
        end, true)
    else
        local storyData = self:getStoryData(item_id)
        if ThemeModel:isPlotRewarded(storyData.id) then
            ImgOn:SetActive(true)
            ImgOff:SetActive(false)
            LockTran:SetActive(false)
            RewardGetedMask:SetActive(true)
            bee.setText(RewardTip, _T("LAB_BUTTON_TEXT_6"))
        else
            ImgOn:SetActive(false)
            ImgOff:SetActive(true)
            LockTran:SetActive(true)
            Effect:SetActive(true)
            LockIcon:SetActive(false)
            bee.setText(StoryTip, _T("LAB_THEME_ACTIVITY5_11"))
            RewardGetedMask:SetActive(false)
            bee.setText(RewardTip, _T("LAB_THEME_ACTIVITY5_12"))
        end

        bee.addClick(item, function()
            StoryModel.storyData = storyData
            bee.logEvent("activity-theme-plot-play", ActivityId.Sports, storyData.id, storyData.group)
            UiManager:showUI("Story", {name = storyData.res, StoryRecord = "SportsLog", StorySkip = "SportsPlot", themeStory = true, hideCb = function()
                local ret = ThemeModel:reqPlotReward(storyData.id, function()
                    -- self:find("hotspring_get_mask", Ani_root):SetActive(true)
                    self:refreshItem(item, item_id)
                end)
                if not StoryModel.isSkip then
                    -- bee.logEvent("galaseason-plot_finish", storyData.id, storyData.group, ret and 1 or 0)
                end
            end})
        end, true)
    end
end

function P:getStoryData(item_id)
    local data = ThemeModel:getConfData()
    if not data then return {} end

    local storys = get_tpl_subKey(tpl_theme_storys_list, "group", data.storys)
    for _, v in ipairs(storys) do
        if v.unlock_item and v.unlock_item[1] == item_id then
            return v
        end
    end
    return {}
end

function P:evt_ItemChangeRSP(msg)
    for _, v in ipairs(msg.item_list) do
        for kk, vv in ipairs(self.item_ids) do
            if v.item_id == vv then
                self:refreshItem(self.Items[kk], vv)
                break
            end
        end
    end
end

function P:hideUI()
    P.super.hideUI(self)
    if self._is_show then
		self:hideTopUI()
	end
end

return P