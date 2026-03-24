local P = class("HotSpringPlot", require("app.views.Hotspring.HotSpringBase"))

function P:onAwake()
    P.super.onAwake(self)
    
    self._tips = {"LAB_STORY_DIALOGUE_S1_1003_01", "LAB_STORY_DIALOGUE_S1_1003_02", "LAB_STORY_DIALOGUE_S1_1003_03"}

    local PiyoList = self:find("PiyoList", self.Right)
    self.Item = self:find("Item", PiyoList)
    self.Item:SetActive(false)

    self.ListPlot = UiListEx:create(PiyoList)
    self.ListPlot:setWidth(164)
    self.ListPlot:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.ListPlot:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100305], true)

    self.ListPlot._list.enabled = false
    self:once(0.15, function()
        local data = tpl_theme_activity[ThemeModel:getConfId()]
        local datas = get_tpl_subKey(tpl_theme_storys_list, "group", data.storys)
        self.ListPlot:setDatas(datas)
        self:once(0.7, function()
            self.ListPlot._list.enabled = true
        end)
    end)
end

function P:refreshItem(data, item, isInit, index)
    local Ani_root = self:find("Ani_root", item)
    
    if isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_2_HotSpringPlot_PiyoList", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_2_HotSpringPlot_PiyoList_idle", Ani_root)
    end

    bee.setText(self:find("TextName", Ani_root), _T(data.title) .. " " .. _T(data.name))
    bee.setText(self:find("hotspring_Item_frame/TextCount", Ani_root), _N(data.rewards[2]))
    self:find("hotspring_get_mask", Ani_root):SetActive(ThemeModel:isPlotRewarded(data.id))
    
    self:find("frame_column_lock", Ani_root):SetActive(data.unlock_time > ThemeModel:getOpenDay() or self:_isUnlockPlod(data))

    bee.addClick(self:find("hotspring_Item_frame", Ani_root), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(data.rewards[1], true), target = self:find("hotspring_Item_frame", Ani_root)})
    end, true)
    bee.addClick(self:find("hotspring_btn_play", Ani_root), function()
        Game:playSound("ui_button_confirm")
        local day = ThemeModel:getOpenDay()
        if data.unlock_time > day then
            UiManager:showToast(_F("LAB_THEME_ACTIVITY1_TIPS_2", data.unlock_time - day))
            return
        end
        if self:_isUnlockPlod(data) then
            UiManager:showToast(_T("LAB_THEME_ACTIVITY1_TIPS_1"))
            return
        end
        bee.logEvent("onsen-plot_play", data.id, data.group)
        StoryModel.hotSpringdata = data
        UiManager:showUI("Story", {name = data.res, hotSpringdata = data, StoryRecord = "HotSpringHallLog", StorySkip = "HotSpringHallSkip", hideCb = function()
            local ret = ThemeModel:reqPlotReward(data.id, function()
                -- self:find("hotspring_get_mask", Ani_root):SetActive(true)
                self.ListPlot:refreshShowingUi()
            end)
            if not StoryModel.isSkip then
                bee.logEvent("onsen-plot_finish", data.id, data.group, ret and 1 or 0)
            end
        end})
    end, true)
    bee.addClick(self:find("frame_column_lock", Ani_root), function()
        Game:playSound("ui_button_confirm")
        local day = ThemeModel:getOpenDay()
        print("==== ggggggg day", day, data.unlock_time)
        if data.unlock_time > day then
            UiManager:showToast(_F("LAB_THEME_ACTIVITY1_TIPS_2", data.unlock_time - day))
            return
        end
        if self:_isUnlockPlod(data) then
            UiManager:showToast(_T("LAB_THEME_ACTIVITY1_TIPS_1"))
            return
        end
    end, true)
end

function P:_isUnlockPlod(data)
    return data.unlock_time > 0 and ThemeModel:getCurPlotId() < data.id - 1
end

