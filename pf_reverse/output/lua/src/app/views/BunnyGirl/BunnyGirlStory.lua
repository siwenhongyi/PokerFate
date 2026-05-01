local P = class("BunnyGirlStory", require("app.views.BunnyGirl.BunnyGirlBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.Entrance = self:find("Entrance", self.Center)

    self.Items = {
        self:find("Item1", self.Entrance),
        self:find("Item2", self.Entrance),
        self:find("Item3", self.Entrance),
    }
    self.item_ids = ThemeModel.BunnyGirlStoryItems
end

function P:onShow()
    P.super.onShow(self)

    for k, v in ipairs(self.Items) do
        self:refreshItem(v, self.item_ids[k])
        local Icon = self:find("Information/Reward/icon_giftpack_03-1", v)
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
    local OnTran = self:find("Main/On", item)
    local OffTran = self:find("Main/Off", item)
    local NormalTran = self:find("Normal", OffTran)
    local LockTran = self:find("Lock", OffTran)
    local StoryIcon = self:find("bunnygirl_story_main_icon_01_on", NormalTran)
    local GrayStoryIcon = self:find("bunnygirl_story_main_icon_01_off", LockTran)
    local RewardTip = self:find("Information/Text/TEXT", item)
    local RewardIcon = self:find("Information/Reward/icon_giftpack_03-1", item)
    local RewardGetedMask = self:find("Information/Reward/bunnygirl_story_reward_icon_done", item)


    local data = ItemModel:getItem(item_id)
    if not data then
        OnTran:SetActive(false)
        OffTran:SetActive(true)
        NormalTran:SetActive(false)
        LockTran:SetActive(true)
        bee.setIcon(StoryIcon, tpl_props[item_id].icon)
        bee.setIcon(GrayStoryIcon, tpl_props[item_id].icon)
        bee.setText(self:find("TEXT", LockTran), _F("LAB_THEME_ACTIVITY4_8", _T(tpl_props[item_id].name)))
        bee.setText(RewardTip, _T("LAB_THEME_ACTIVITY3_12"))
        bee.setIcon(RewardIcon, tpl_props[item_id].icon)
        RewardGetedMask:SetActive(false)

        bee.addClick(item, function()
            UiManager:showUI("BunnyGirlNotice", {
                text = _F("LAB_THEME_ACTIVITY4_9", _T(tpl_props[item_id].name)),
                onSure = function()
                    UiManager:showUI("BunnyGirlShop")
                end,
            })
        end, true)
    else
        local storyData = self:getStoryData(item_id)
        if ThemeModel:isPlotRewarded(storyData.id) then
            OnTran:SetActive(true)
            OffTran:SetActive(false)
            RewardGetedMask:SetActive(true)
            bee.setText(RewardTip, _T("LAB_BUTTON_TEXT_6"))
        else
            OnTran:SetActive(false)
            OffTran:SetActive(true)
            NormalTran:SetActive(true)
            LockTran:SetActive(false)
            RewardGetedMask:SetActive(false)
            bee.setText(RewardTip, _T("LAB_THEME_ACTIVITY3_12"))
        end

        bee.addClick(item, function()
            StoryModel.storyData = storyData
            -- bee.logEvent("galaseason-plot_play", storyData.id, storyData.group)
            UiManager:showUI("Story", {name = storyData.res, StoryRecord = "BunnyGirlLog", StorySkip = "BunnyGirlPlot", hideCb = function()
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