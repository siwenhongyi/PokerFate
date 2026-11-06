-- 事务所解锁确认弹窗
-- 确认是否消耗道具解锁事务所
local P = class("DispatchUnlock", UiDialog)

function P:onAwake()
    local Panel = self:find("AnimRoot/Center/Panel")

    -- 标题
    self.TextTitle = self:find("TextTitle", Panel)
    self.TextTip = self:find("TextTip", Panel)

    -- 道具节点 (Item01)
    self.Item01 = self:find("Item01", Panel)
    self.TextNum = self:find("TextNum", self.Item01)

    self.TextCheck = self:find("TextCheck", Panel)
    self.ToggleCheck = self:find("TextCheck/ToggleCheck", Panel)

    -- 关闭按钮事件
    bee.addClick(self:find("CloseButton", Panel), function()
        self:onBtClose()
    end)

    -- 点击遮罩关闭
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:onBtClose()
    end)

    bee.addClick(self:find("ConfirmButton", Panel), function()
        if not bee.checkCd("Unlock/afk/upCampLevel", 2) then
            return
        end
        Game:playSound("ui_button_confirm")
        local item = ItemModel:getItem(GPropId.CampDispatchUpgrade, true)
        if item.num < self._cost then
            bee.logEvent("dispatch-camp-levelup", self.camp_id, 0)
            UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(item.name)))
            return
        end
        local camp_id = self.camp_id
        Net:post("afk/upCampLevel", {camp_id = self.camp_id, item_num = self._cost}, function(d)
            if 0 == d.code then
                bee.logEvent("dispatch-camp-levelup", camp_id, 1)
                DispatchModel:setCampLevel(camp_id, d.camp_level)
                if bee.isCheck(self.ToggleCheck) then
                    LocalStore:isDailyTagValidCrossDay("DispatchModel_upgradeCamp" .. PlayerModel:getUid())
                end
                if 1 == self._level then
                    UiManager:showToast(_F("LAB_DISPATCH_50", _T(tpl_camp_detail[camp_id].camp_name)))
                else
                    UiManager:showUI("DispatchLevel", {camp_id = camp_id})
                end
                if self._params and self._params.cb then
                    self._params.cb()
                end
                DispatchModel:reqEventList()
            else
                bee.logEvent("dispatch-camp-levelup", camp_id, 0)
            end
        end)
        self:hideUI()
    end)

    bee.addClick(self:find("CancelButton", Panel), function()
        self:onBtClose()
    end)
end

function P:onShow()
    local params = self._params or {}

    self.camp_id = params.camp_id or 0

    self._level = DispatchModel:getCampLevel(self.camp_id) + 1
    local d = tpl_camp_info[self._level]
    self._cost = self.camp_id == 0 and d.quality_up_cost1 or d.quality_up_cost2

    self.TextCheck:SetActive(self._level > 1)

    if self._level > 1 then
        bee.setText(self.TextTitle, _F("LAB_DISPATCH_43", _T(tpl_camp_detail[self.camp_id].camp_name)))
        bee.setText(self.TextTip, _T("LAB_DISPATCH_44"))
    else
        bee.setText(self.TextTitle, _F("LAB_DISPATCH_47", _T(tpl_camp_detail[self.camp_id].camp_name)))
        bee.setText(self.TextTip, _T("LAB_DISPATCH_48"))
    end

    PropItem:create(self.Item01, ItemModel:getItem(GPropId.CampDispatchUpgrade, true)):bindTips()
    self:evt_ItemChangeRSP()
end

function P:evt_ItemChangeRSP(msg)
    local num = ItemModel:getItemNumById(GPropId.CampDispatchUpgrade)
    if num >= self._cost then
        bee.setText(self.TextNum, _N2(self._cost))
    else
        bee.setText(self.TextNum, _F("<color=#DA3838>{p1}</color>", _N2(self._cost)))
    end
end

return P