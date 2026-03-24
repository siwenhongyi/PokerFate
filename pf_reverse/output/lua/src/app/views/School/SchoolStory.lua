local P = class("SchoolStory", require("app.views.School.SchoolBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.Entrance = self:find("Entrance", self.Center)

    self.Items = {
        self:find("Item1", self.Entrance),
        self:find("Item2", self.Entrance),
        self:find("Item3", self.Entrance),
    }
    self.item_ids = ThemeModel.SchoolStoryItems
end

function P:onShow()
    P.super.onShow(self)

    for k, v in ipairs(self.Items) do
        self:refreshItem(v, self.item_ids[k])
        local Icon = self:find("Item1/icon_giftpack_03-1", v)
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
    local LockTip = self:find("Lock/Text", item)
    local RewardTip = self:find("Item1/Text", item) 
    local GetedMask = self:find("Item1/school_story_img_done", item)

    local RoleShadow = self:find("school_story_img_character_1", item)
    local RoleIcon = self:find("school_story_img_character", item)
    local ItemIcon = self:find("Lock/school_main_button_task", item)
    local LockIcon = self:find("Lock/school_story_img_lock", item)
    local Effect = self:find("Lock/Effect", item)

    local data = ItemModel:getItem(item_id)
    if not data then
        bee.setText(LockTip, _F("LAB_THEME_ACTIVITY2_8", _T(tpl_props[item_id].name)))
        bee.setText(RewardTip, _T("LAB_THEME_ACTIVITY3_12"))
        bee.setIcon(ItemIcon, tpl_props[item_id].icon)
        GetedMask:SetActive(false)
        RoleShadow:SetActive(true)
        RoleIcon:SetActive(false)
        LockIcon:SetActive(true)
        Effect:SetActive(false)

        bee.addClick(item, function()
            UiManager:showUI("SchoolNotice", {
                text = _F("LAB_THEME_ACTIVITY2_9",  "<color=#FBE57E>" .. _T(tpl_props[item_id].name) .. "</color>" ),
                onSure = function()
                    UiManager:showUI("SchoolShop")
                end,
            })
        end, true)
    else
        local storyData = self:getStoryData(item_id)
        LockIcon:SetActive(false)
        if ThemeModel:isPlotRewarded(storyData.id) then
            RoleShadow:SetActive(false)
            RoleIcon:SetActive(true)
            GetedMask:SetActive(true)
            Effect:SetActive(false)
            bee.setText(LockTip, _T(""))
            bee.setText(RewardTip, _T("LAB_BUTTON_TEXT_6"))
        else
            RoleShadow:SetActive(true)
            RoleIcon:SetActive(false)
            GetedMask:SetActive(false)
            Effect:SetActive(true)
            bee.setText(LockTip, _T("LAB_THEME_ACTIVITY2_11"))
            bee.setText(RewardTip, _T("LAB_THEME_ACTIVITY3_12"))
        end

        bee.addClick(item, function()
            StoryModel.storyData = storyData
            -- bee.logEvent("galaseason-plot_play", storyData.id, storyData.group)
            UiManager:showUI("Story", {name = storyData.res, StoryRecord = "SchoolLog", StorySkip = "SchoolPlot", hideCb = function()
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

