local P = class("GalaSeasonInvitation", require("app.views.GalaSeason.GalaSeasonBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.Entrance = self:find("Entrance", self.Center)

    self.Items = {
        self:find("Item1", self.Entrance),
        self:find("Item2", self.Entrance),
        self:find("Item3", self.Entrance),
    }
    self.item_ids = ThemeModel.GalaStoryItems
end

function P:onShow()
    P.super.onShow(self)

    for k, v in ipairs(self.Items) do
        self:refreshItem(v, self.item_ids[k])
        local Icon = self:find("Information/gala_invitation_reward_bg/Icon", v)
        bee.addClick(Icon, function()
            Game:playSound("ui_button_confirm")
            local storyData = self:getStoryData(self.item_ids[k])
            if storyData then
                bee.setIcon(Icon, tpl_props[storyData.rewards[1]].icon)
                UiManager:showUI("CommonItemTip", {data = {id = storyData.rewards[1]}, target = Icon})
            end
        end)
            
    end
end

function P:refreshItem(item, item_id)
    local data = ItemModel:getItem(item_id)
    if not data then
        self:find("Information/TextNeed", item):SetActive(true)
        self:find("Information/TextGet", item):SetActive(false)
        self:find("Information/gala_invitation_reward_mask", item):SetActive(false)
        bee.setText(self:find("Information/TextNeed", item), _F("LAB_THEME_ACTIVITY2_8", _T(tpl_props[item_id].name)))

        self:find("Main/on", item):SetActive(false)
        self:find("Main/off", item):SetActive(true)
        self:find("Main/off/Lock", item):SetActive(true)
        self:find("Main/off/Normal", item):SetActive(false)

        bee.addClick(item, function()
            UiManager:showTip({
                text = _F("LAB_THEME_ACTIVITY2_9", _T(tpl_props[item_id].name)),
                onSure = function()
                    UiManager:showUI("GalaSeasonShop")
                end,
            })
        end, true)
    else
        self:find("Information/TextNeed", item):SetActive(false)
        self:find("Main/off/Lock", item):SetActive(false)
        self:find("Main/off/Normal", item):SetActive(true)

        local storyData = self:getStoryData(item_id)
        if ThemeModel:isPlotRewarded(storyData.id) then
            self:find("Main/on", item):SetActive(true)
            self:find("Main/off", item):SetActive(false)
            self:find("Information/TextNeed", item):SetActive(false)
            self:find("Information/TextGet", item):SetActive(false)
            self:find("Information/gala_invitation_reward_mask", item):SetActive(true)
        else
            self:find("Main/on", item):SetActive(false)
            self:find("Main/off", item):SetActive(true)
            self:find("Information/TextNeed", item):SetActive(false)
            self:find("Information/TextGet", item):SetActive(true)
            self:find("Information/gala_invitation_reward_mask", item):SetActive(false)
        end
        bee.addClick(item, function()
            StoryModel.storyData = storyData
            bee.logEvent("galaseason-plot_play", storyData.id, storyData.group)
            UiManager:showUI("Story", {name = storyData.res, StoryRecord = "GalaSeasonLog", StorySkip = "GalaSeasonPlot", hideCb = function()
                local ret = ThemeModel:reqPlotReward(storyData.id, function()
                    -- self:find("hotspring_get_mask", Ani_root):SetActive(true)
                    self:refreshItem(item, item_id)
                end)
                if not StoryModel.isSkip then
                    bee.logEvent("galaseason-plot_finish", storyData.id, storyData.group, ret and 1 or 0)
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

