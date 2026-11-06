-- 加速确认弹窗
-- 选择加速道具数量，确认加速派遣
local P = class("DispatchAccelerate", UiDialog)

function P:onAwake()
    local Panel = self:find("AnimRoot/Center/Panel")

    -- 道具信息
    self.Information = self:find("Information", Panel)
    self.ItemObj = self:find("Item", self.Information)
    self.TextName = self:find("TextName", self.Information)
    self.TextDec = self:find("TextScrollView/Viewport/Content/TextDec", self.Information)

    self.TextTime = self:find("Time/TextTime", Panel)

    local Quantity = self:find("Quantity", Panel)
    self.TextNum = self:find("TextNum", Quantity)

    -- 数量按钮
    self.MinButton01 = self:find("MinButton01", Quantity)
    self.MaxButton01 = self:find("MaxButton01", Quantity)
    self.MinusButton01 = self:find("MinSButton01", Quantity)
    self.PlusButton01 = self:find("PlusButton01", Quantity)

    self.MinButton02 = self:find("MinButton02", Quantity)
    self.MaxButton02 = self:find("MaxButton02", Quantity)
    self.MinusButton02 = self:find("MinSButton02", Quantity)
    self.PlusButton02 = self:find("PlusButton02", Quantity)

    -- 操作按钮
    self.AccelerateButton = self:find("AccelerateButton", Panel)

    -- 关闭
    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
end

function P:onStart()
    -- 确认加速
    bee.addClick(self.AccelerateButton, function()
        if not bee.checkCd("post_afk/speed", 2) then
            return
        end
        local eventCfg = tpl_event_info[self.event.event_id]
        bee.logEvent("dispatch-speeded-up", eventCfg.campInt, self.event.event_id)
        Game:playSound("ui_button_confirm")
        local item = ItemModel:getItem(GPropId.AccelerateDispatch, true)
        if item.num < self._selectedCount then
            UiManager:showUI("DispatchSeasonPass", {index = 3})
            UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(item.name)))
            return
        end
        local dt = 0
        if self.event then
            dt = self.event.end_ts - bee.getServerTime()
        end
        if dt <= 0 then
            UiManager:showToast(_T("LAB_DISPATCH_27"))
            self:hideUI()
            return
        end
        self._isInSpeed = true
        Net:post("afk/speed", {id = self.event.id, item_num = self._selectedCount}, function(d)
            self._isInSpeed = nil
            if 0 == d.code then
                self._isClosed = true
                DispatchModel:setEventEndTime(self.event.id, d.end_ts)
                DispatchModel:sortEventList()
                if self._params and self._params.cb then
                    self._params.cb()
                end
                bee.emit("evt_updateLobbyDispatchAnim")
                self:hideUI()
            end
        end, function()
            self._isInSpeed = nil
        end)
    end)

    --  最小数量
    bee.addClick(self.MinButton01, function()
        Game:playSound("ui_button_confirm")
        self._selectedCount = 1
        self:refreshNumText()
    end)
    bee.addClick(self.MinButton02, function()
		UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
    end)

    -- 最大数量
    bee.addClick(self.MaxButton01, function()
        Game:playSound("ui_button_confirm")
        self._selectedCount = self._maxCount
        self:refreshNumText()
    end)
    bee.addClick(self.MaxButton02, function()
		UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
    end)

    -- 减一
    bee.addClick(self.MinusButton01, function()
        if self._selectedCount <= 1 then
            UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
            return
        end
        Game:playSound("ui_button_confirm")
        self._selectedCount = math.max(1, self._selectedCount - 1)
        self:refreshNumText()
    end)
    bee.addClick(self.MinusButton02, function()
        UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
    end)

    -- 加一
    bee.addClick(self.PlusButton01, function()
        if self._selectedCount >= self._maxCount then
            UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
            return
        end
        Game:playSound("ui_button_confirm")
        self._selectedCount = math.min(self._maxCount, self._selectedCount + 1)
        self:refreshNumText()
    end)
    bee.addClick(self.PlusButton02, function()
        UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
    end)
end

function P:evt_refreshTopInfo()
    if not self._isInSpeed and not self._isClosed then
        self:refreshUI()
    end
end

function P:onShow()
    local params = self._params or {}

    self.event = params.event or nil
    self._selectedCount = 1

    self:refreshUI()

    local dt = 0
    if self.event then
        dt = self.event.end_ts - bee.getServerTime()
    end
    bee.setText(self.TextTime, TimeHelp:getTimeStr(dt))
    self:schedule(1, function()
        dt = dt - 1
        if self._isClosed then
            return
        end
        if dt <= 0 then
            dt = 0
            UiManager:showToast(_T("LAB_DISPATCH_27"))
            self:hideUI()
            return
        end
        bee.setText(self.TextTime, TimeHelp:getTimeStr(dt))
        local num = math.ceil(dt / tpl_constdata.Dispatch_Speedup)
        local item = ItemModel:getItem(GPropId.AccelerateDispatch, true)
        self._maxCount = math.max(math.min(item.num, num), 1)
    end)
end

function P:refreshUI()
    local item = ItemModel:getItem(GPropId.AccelerateDispatch, true)

    -- 道具数据
    PropItem:create(self.ItemObj, item)

    -- 道具名称
    bee.setText(self.TextName, _T(item.name))
    bee.setText(self.TextDec, ItemModel:getItemDesText(item.id))

    self:find("Owend", self.Information):SetActive(item.num > 0)
    self:find("Not Owend", self.Information):SetActive(item.num <= 0)
    if item.num > 0 then
        bee.setText(self:find("Owend", self.Information), _T("LAB_BACKPACK_DES_22") .. _N(item.num))
    end

    -- 最大可用数量
    local dt = 0
    if self.event then
        dt = self.event.end_ts - bee.getServerTime()
    end
    local num = math.ceil(dt / tpl_constdata.Dispatch_Speedup)
    self._maxCount = math.max(math.min(item.num, num), 1)
    self:refreshNumText()
end

function P:refreshNumText()
    if self.TextNum then
        bee.setText(self.TextNum, tostring(self._selectedCount))
    end

    self.MinButton01:SetActive(self._selectedCount > 1)
    self.MaxButton01:SetActive(self._selectedCount < self._maxCount)
    self.MinusButton01:SetActive(self._selectedCount > 1)
    self.PlusButton01:SetActive(self._selectedCount < self._maxCount)

    self.MinButton02:SetActive(self._selectedCount == 1)
    self.MaxButton02:SetActive(self._selectedCount == self._maxCount)
    self.MinusButton02:SetActive(self._selectedCount == 1)
    self.PlusButton02:SetActive(self._selectedCount == self._maxCount)
end

return P