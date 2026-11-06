local P = class("AchievementRecord", UiDialog)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")
    self.RecordList = self:find("Panel/RecordList", self.Center)
    self.Item = self:find("Item01", self.RecordList)
    self.Item:SetActive(false)
    self.Title = self:find("Panel/Title", self.Center)

    self.TipRoot = self:find("Tips", self.Center)
    self.SingleLineTip = self:find("SingleLine", self.TipRoot)
    self.TwoLineTip = self:find("TwoLines", self.TipRoot)
    local testText = self:find("TestText", self.TipRoot)
    self.TestTextTran = testText:GetComponent("RectTransform")
    self.TestText = testText:GetComponent("Text")
    self.TipMask = self:find("TipMask", self.Center)

    --Scroll
    self.ItemList = UiListEx:create(self.RecordList)
    self.ItemList:setWidth(220)
    self.ItemList:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.ItemList:setRefreshFunc(function(data, item, isInit, index)
        self:refreshThemeItem(data, item, isInit, index)
    end)

    bee.addClick(self:find("Panel/common_button_close_01", self.Center), function ()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)

    bee.addClick(self.TipMask, function ()
        Game:playSound("ui_button_confirm")
        self.TipMask:SetActive(false)
        self.SingleLineTip:SetActive(false)
        self.TwoLineTip:SetActive(false)
    end)
end

function P:onShow()
    AchievementModel:requestRecentlyAchTask()
end

function P:evt_refreshRecentlyAchievement(data)
    local list = {}
    for _,v in pairs(data) do
        if tpl_achievement_task[v.task_id] ~= nil then
            table.insert(list, v)
        end
    end

    table.sort(list, function(a, b)
        if a.created_at == b.created_at then
            return a.task_id > b.task_id
        else
            return a.created_at > b.created_at
        end
    end)
    self.ItemList:setDatas(list)
end

function P:refreshThemeItem(data, item, isInit, index)
    local cfg = tpl_achievement_task[data.task_id]
    local themeCfg = tpl_achievement_theme[cfg.ach_type]
    bee.setText(self:find("Information/Title", item), _T(themeCfg.name))
    bee.setText(self:find("Information/Text", item), _T(cfg.name))
    local timeDate = TimeHelp:getDateTimeStr(data.created_at, "/", ":")
    local dates = string.split(timeDate, " ")
    bee.setText(self:find("Information/Time/Date", item), dates[1])
    bee.setText(self:find("Information/Time/Time", item), dates[2])
    local iconGo = self:find("icon", item)
    bee.setIcon(iconGo, string.format("achievement_level_%s", cfg.ach_level), "Achievement", true)
    bee.addClick(item, function ()
        self:getTip(data, iconGo.transform.position)
    end, true)
end

function P:getTip(data, pos)
    local cfg = tpl_achievement_task[data.task_id]
    self.SingleLineTip:SetActive(false)
    self.TwoLineTip:SetActive(false)
    --所需条件值
    local needValue, gameStr = AchievementModel:getDesValue(cfg)
    local str = _F(cfg.des, _N(needValue), gameStr)
    if cfg.task_type == 204 then
        local nameStr = _T(tpl_character[cfg.value[1]].name)
        str = _F(cfg.des, nameStr)
    end
    self.TestText.text = str
    local moreLine = self.TestText.preferredWidth > self.TestTextTran.sizeDelta.x
    local tip = moreLine and self.TwoLineTip or self.SingleLineTip
    tip:SetActive(true)
    bee.setText(self:find("Information/Title", tip), _T(cfg.name))
    bee.setText(self:find("Information/Text", tip), str)
    local clearRate = AchievementModel:getAllServerProgress(data.rate, data.finish)
    bee.setText(self:find("Information/Tip", tip), _F("TAB_ACHIEVEMENT_8", clearRate))
    bee.setIcon(self:find("icon", tip), string.format("achievement_level_%s", cfg.ach_level), "Achievement", true)
    self.TipMask:SetActive(true)
    tip.transform.position = pos
    self:checkTipLimit(moreLine and 2 or 1)
    return tip
end

function P:checkTipLimit(index)
    local uiRoot = UiManager:getUiRoot()
    if uiRoot == nil then
        return
    end
    local height = uiRoot:GetComponent("RectTransform").sizeDelta.y
    if index == 1 then
        local rectTran = self.SingleLineTip:GetComponent("RectTransform")
        local bg = self:find("bg", rectTran)
        local line = self:find("achievement_record_bg_02", bg)
        local dif = height * 0.5 - rectTran.sizeDelta.y
        if rectTran.localPosition.y < -dif then
            bg.transform.localScale = bee.v3(1, -1, 1)
            bg.transform.localPosition = bee.v3(bg.transform.localPosition.x, -154.5, bg.transform.localPosition.z)
            line.transform.localPosition = bee.v3(78.5, -35, 0)
            rectTran.localPosition = bee.v3(rectTran.localPosition.x, rectTran.localPosition.y + 290, rectTran.localPosition.z)
        else
            bg.transform.localScale = bee.v3(1, 1, 1)
            bg.transform.localPosition = bee.v3(bg.transform.localPosition.x, -114.5, bg.transform.localPosition.z)
            line.transform.localPosition = bee.v3(78.5, -5, 0)
        end
    else
        local rectTran = self.TwoLineTip:GetComponent("RectTransform")
        local bg = self:find("bg", rectTran)
        local line = self:find("achievement_record_bg_02", bg)
        local dif = height * 0.5 - rectTran.sizeDelta.y
        if rectTran.localPosition.y < -dif then
            bg.transform.localScale = bee.v3(1, -1, 1)
            bg.transform.localPosition = bee.v3(bg.transform.localPosition.x, -175, bg.transform.localPosition.z)
            line.transform.localPosition = bee.v3(78.5, -58, 0)
            rectTran.localPosition = bee.v3(rectTran.localPosition.x, rectTran.localPosition.y + 310, rectTran.localPosition.z)
        else
            bg.transform.localScale = bee.v3(1, 1, 1)
            bg.transform.localPosition = bee.v3(bg.transform.localPosition.x, -131, bg.transform.localPosition.z)
            line.transform.localPosition = bee.v3(78.5, 11, 0)
        end
    end
end

return P