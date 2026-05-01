local P = class("GameGuide", UiBase)

local GuideKind = {
    Story = 1, -- 播放剧情
    Ui = 2,     -- 指向ui
    Draw = 3,   -- 抽卡动画
    Emoji = 4,  -- 表情动画
    Chat = 5,   -- 聊天气泡
    WaitScene = 6, -- 等待场景
}

-- 新手引导
function P:onAwake()
    -- self.inPop = true
    self.Bg = self:find("Bg")
    self.Hollow = self:find("Hollow")
    self.Finger = self:find("Finger")
    self.ImageTip = self:find("ImageTip")
    self.BgTipUi = self:find("BgTipUi")
    self.GuideHand = self:find("GuideHand", self.Finger)
    self.GuideSpine = self:find("GuideSpine", self.Finger)

    bee.addClick(self.Bg, function() self:_checkNext() end)
    self.BgButton = self.Bg:GetComponent("Button")
    self.ImageTipPos = self.ImageTip.transform.localPosition
end

function P:onShow()
    bee.setSortingOrder(self.node, 32767)
    self._datas = get_tpl_subKey(tpl_guide_list, "guide", self._params.guide)
    if self._params.data then
        self._data = self._params.data
    else
        self._data = self._datas[1]
    end
    self.InitHollow = false
    self.HollowItems = {}
    self:initUI(false, self._params.delay)
    self:initEvent()
end

function P:onDestroy()
    P.super.onDestroy(self)
end

function P:showUI()
    self.ImageTip:SetActive(false)
    self.Finger:SetActive(false)
    bee.setOpacity(self.Bg, 0)

    UiManager:showUI(self._data.uiName, {closeCallback = function()
        if self:_checkNext() then
            bee.emit("evt_guide_skip")
        end
    end, data = self._data})
end

function P:initUI(fade, delay)
    if self._fadeAct then
        self._fadeAct:kill()
        self._fadeAct = nil
    end
    if self._fadeAct2 then
        self._fadeAct2:Kill()
        self._fadeAct2 = nil
    end
    if self._act then
        self._act:kill()
        self._act = nil
    end
    
    self.ImageTip:SetActive(false)
    self.Finger:SetActive(false)
    self.Hollow:SetActive(false)

    bee.setOpacity(self.Bg, 0)
    self.BgButton.enabled = false
    if GuideKind.Ui == self._data.kind then
        if delay then
            self:once(delay, function()
                if self._data.hide_mask == 1 then
                else
                    bee.setOpacity(self.Bg, 0.8)
                end
                self:showUiTip(fade)
            end)
        else
            if self._data.hide_mask == 1 then
                bee.setOpacity(self.Bg, 0)
            else
                bee.setOpacity(self.Bg, 0.8)
            end

            self:showUiTip(fade)
        end
    elseif GuideKind.Emoji == self._data.kind then
        bee.emit("evt_FaceBRC", {code = 0, seatid = self._data.p1[1], id = self._data.p1[2]})
        self:once(-1, function() self:_checkNext() end)
    elseif GuideKind.Chat == self._data.kind then
        bee.emit("evt_TextBRC", {code = 0, seatid = self._data.p1[1], id = self._data.p1[2]})
        self:once(-1, function() self:_checkNext() end)
    elseif GuideKind.WaitScene == self._data.kind then
        self._waitSceneName = self._data.v1
    end
end

function P:initEvent()
end

function P:showImageTip(empty)
    if self._data.tip and self._data.tip_pos then
        self.ImageTip:SetActive(true)
        if GameModel.data then
            local info = GameModel.data:getMyPlayerInfo()
            local board = GameModel.data:getBoardInfo()
            local _, cardType = PKHelper.getCardType(info.hand_cards, board, GameModel.data:getRoomType())
            bee.setText(self:find("Tips/Text", self.ImageTip), _F(self._data.tip, _T(cardType)))
        else
            bee.setText(self:find("Tips/Text", self.ImageTip), _T(self._data.tip))
        end
        local pos = bee.v3(self._data.tip_pos[1], self._data.tip_pos[2])
        if Config.DIR_UP == self._data.tip_pos[4] then
            pos.y = SCREEN_HEIGHT_SAFE / 2 - (DESIGN_HEIGHT / 2 - pos.y)
        elseif Config.DIR_RIGHT == self._data.tip_pos[4] then
            pos.x = SCREEN_WIDTH_SAFE / 2 - (DESIGN_WIDTH / 2 - pos.x)
        elseif Config.DIR_DOWN == self._data.tip_pos[4] then
            pos.y = -SCREEN_HEIGHT_SAFE / 2 - (-DESIGN_HEIGHT / 2 - pos.y)
        elseif Config.DIR_LEFT == self._data.tip_pos[4] then
            pos.x = -SCREEN_WIDTH_SAFE / 2 - (-DESIGN_WIDTH / 2 - pos.x)
        elseif 14 == self._data.tip_pos[4] then
            pos.y = SCREEN_HEIGHT_SAFE / 2 - (DESIGN_HEIGHT / 2 - pos.y)
            pos.x = -SCREEN_WIDTH_SAFE / 2 - (-DESIGN_WIDTH / 2 - pos.x)
        elseif 12 == self._data.tip_pos[4] then
            pos.y = SCREEN_HEIGHT_SAFE / 2 - (DESIGN_HEIGHT / 2 - pos.y)
            pos.x = SCREEN_WIDTH_SAFE / 2 - (DESIGN_WIDTH / 2 - pos.x)
        elseif 34 == self._data.tip_pos[4] then
            pos.y = -SCREEN_HEIGHT_SAFE / 2 - (-DESIGN_HEIGHT / 2 - pos.y)
            pos.x = -SCREEN_WIDTH_SAFE / 2 - (-DESIGN_WIDTH / 2 - pos.x)
        elseif 32 == self._data.tip_pos[4] then
            pos.y = -SCREEN_HEIGHT_SAFE / 2 - (-DESIGN_HEIGHT / 2 - pos.y)
            pos.x = SCREEN_WIDTH_SAFE / 2 - (DESIGN_WIDTH / 2 - pos.x)
        end
        self.ImageTip.transform.localPosition = pos
        if Config.DIR_UP == self._data.tip_pos[3] then
            self:find("Tips", self.ImageTip).transform.localPosition = bee.v3(0, 270)
        elseif Config.DIR_RIGHT == self._data.tip_pos[3] then
            self:find("Tips", self.ImageTip).transform.localPosition = bee.v3(600, 0)
        elseif Config.DIR_DOWN == self._data.tip_pos[3] then
            self:find("Tips", self.ImageTip).transform.localPosition = bee.v3(0, -270)
        elseif Config.DIR_LEFT == self._data.tip_pos[3] then
            self:find("Tips", self.ImageTip).transform.localPosition = bee.v3(-600, 0)
        end
    else
        self.ImageTip:SetActive(false)
    end

    local emptyTran = self:find("EmptyText", self.ImageTip):GetComponent("RectTransform")
    if empty then
        emptyTran.gameObject:SetActive(true)
        local tipsTran = self:find("Tips", self.ImageTip):GetComponent("RectTransform")
        local tipsText = self:find("Tips/Text", self.ImageTip):GetComponent("Text")
        emptyTran.localPosition = bee.v3(tipsTran.localPosition.x, tipsTran.localPosition.y - (tipsText.preferredHeight + 60) * 0.5 - 30, 0)
        if tipsTran.localPosition.y > 0 then
            local roleImage = self:find("Image", self.ImageTip)
            local posY = tipsTran.localPosition.y - tipsText.preferredHeight * 0.5 - emptyTran.sizeDelta.y - 319 * 0.5
            roleImage.transform.localPosition = bee.v3(0, posY, 0)
        end
    else
        emptyTran.gameObject:SetActive(false)
    end
end

function P:showUiTip()
    self:hideUiTip()

    self._clickUi = {}
    -- if self._data.click_ui then
    --     local n = bee.find(self._data.click_ui, UiManager:getUiRoot())
    --     if n then
    --         ui._stopClick = nil
            
    --         self.Finger.transform.position = n.transform.position
            
    --         if not fade then
    --             self.Finger:SetActive(true)
    --         end
    --         local cb = function()
    --             self:_checkNext()
    --         end
    --         bee.addClick2(n, cb)
    --         self._clickUi[n] = cb
    --     end
    -- end

    self._tipUis = {}
    self._tipWaitUis = {}
    if self._data.is_weak then
        self:weakGuide()
    else
        self:forceGuide()
    end
    
    if self._data.hide_ui then
        self._hideUis = {}
        for _, v in ipairs(self._data.hide_ui) do
            local n = bee.find(v, UiManager:getUiRoot())
            if n then
                n:SetActive(false)
                self._hideUis[n] = n
            end
        end
    end
end

--强引导
function P:forceGuide()
    local isWait = false
    if self._data.show_ui then
        local uis = self._data.show_ui
        if self._data.delay then
            bee.setOpacity(self.Bg, 0)
        end
        self:once(self._data.delay or 0.05, function()
            if self._data.delay then
                if self._data.hide_mask == 1 then
                else
                    bee.setOpacity(self.Bg, 0.8)
                end
            end
            if self._data.show_ui == uis then
                for _, v in ipairs(self._data.show_ui) do
                    local n = bee.find(v, UiManager:getUiRoot())
                    if n then
                        if self:_checkUiVisible(n) then
                            self:addShowUiTip(n)
                        else
                            self._tipWaitUis[n] = n
                            isWait = true
                        end
                    else
                        isWait = true
                    end
                end
            end
            if not isWait then
                self:showImageTip(false)
            end
        end)
    else
        self:_checkNext()
    end
end

--弱引导
function P:weakGuide()
    if self._data.delay then
        bee.setOpacity(self.Bg, 0)
    end
    -- self.Hollow:SetActive(false)

    if self._data.show_ui then
        local hollowAction = function()
            if self._data.show_ui then
                local uis = self._data.show_ui
                if self._data.show_ui == uis then
                    for _, v in ipairs(self._data.show_ui) do
                        local n = bee.find(v, UiManager:getUiRoot())
                        if n then
                            if self._data.show_area then
                                local pos = n.transform.position
                                self:setHollow(true, pos, self._data.show_area)
                            else
                                self:addShowUiTip(n)
                            end
                        end
                    end
                end
            else
                self:setHollow(false)
            end
            self.BgButton.enabled = true
            self:showImageTip(true)
        end

        if self._data.delay then
            self:once(self._data.delay , function()
                if self._data.hide_mask == 1 then
                else
                    bee.setOpacity(self.Bg, 0.8)
                end
                hollowAction()
            end)
        else
            hollowAction()
        end
    else
        self.BgButton.enabled = true
        self:showImageTip(true)
    end

    
end

function P:addShowUiTip(n)
    -- self._tipUis[n] = n.transform.parent
    -- n.transform:SetParent(self.BgTipUi.transform)
    local tipUi = CU.GameObject.Instantiate(n, self.BgTipUi.transform, true)
    local animators = tipUi:GetComponentsInChildren(typeof(CU.Animator))
    if animators then
        for i = 0, animators.Length - 1 do
            animators[i].enabled = false
        end
    end
    self._tipUis[n] = tipUi
    n.transform.localScale = bee.v3zero
    local cb = function()
        if self.__guideClickDt == scheduler.timeSpend then return end
		self.__guideClickDt = scheduler.timeSpend
        if not self._needClickNum then
            self:hideUiTip()
        end
        local cmp = n:GetComponent("Button")
        if cmp then
            cmp.onClick:Invoke()
        else
            cmp = n:GetComponent("Toggle")
            if cmp then
                cmp.isOn = true
                cmp.onValueChanged:Invoke(true)
            end
        end
        if self._needClickNum then
            self._needClickNum = self._needClickNum - 1
            if self._needClickNum > 0 then
                return
            end
            self._needClickNum = nil
        end
        self:_checkNext()
        self:_checkLog()
    end
    local tipbtn = tipUi:GetComponent("Button")
    if not bee.isNull(tipbtn) then
        bee.addClick2(tipUi, cb)
    end
    local tiptoggle = tipUi:GetComponent("Toggle")
    if not bee.isNull(tiptoggle) then
        bee.onCheck(tipUi, cb)
    end
    self._clickUi[tipUi] = cb
    self._needClickNum = nil
    if self._data.finger then
        self.Finger:SetActive(true)
        self.GuideHand:SetActive(self._data.finger_kind ~= 2)
        self.GuideSpine:SetActive(self._data.finger_kind == 2)
        self._needClickNum = self._data.finger_kind == 2 and 2 or nil
        local transform = self.Finger.transform
        transform.localPosition = bee.v3Add(tipUi.transform.localPosition, bee.v3(self._data.finger[1] or 0, self._data.finger[2] or 0))
        if self._data.finger_rotate then
            transform.localScale = bee.v3(self._data.finger_rotate[1], self._data.finger_rotate[2], 1)
            transform.localEulerAngles = bee.v3(0, 0, self._data.finger_rotate[3])
        else
            transform.localScale = bee.v3one
            transform.localEulerAngles = bee.v3zero
        end
    end
end

function P:addShowUiTipWithOutClick(n)
    local tipUi = CU.GameObject.Instantiate(n, self.BgTipUi.transform, true)
    local animators = tipUi:GetComponentsInChildren(typeof(CU.Animator))
    if animators then
        for i = 0, animators.Length - 1 do
            animators[i].enabled = false
        end
    end
    local images = tipUi:GetComponentsInChildren(typeof(CU.UI.Image))
    if images then
        for i = 0, images.Length - 1 do
            images[i].raycastTarget = false
        end
    end
    self._tipUis[n] = tipUi
    n.transform.localScale = bee.v3zero
end

function P:hideUiTip()
    if self._tipUis then
        for k, v in pairs(self._tipUis) do
            -- k.transform:SetParent(v, true)
            k.transform.localScale = bee.v3one
            CU.GameObject.Destroy(v)
        end
        self._tipUis = nil
    end
    if self._clickUi then
        for k, v in pairs(self._clickUi) do
            local tipbtn = k:GetComponent("Button")
            if not bee.isNull(tipbtn) then
                bee.removeClick(k, v)
            end
            local tiptoggle = k:GetComponent("Toggle")
            if not bee.isNull(tiptoggle) then
                bee.removeCheck(k)
            end
        end
        self._clickUi = nil
    end
    self._tipWaitUis = nil
    if self._hideUis then
        for k, v in pairs(self._hideUis) do
            k:SetActive(true)
        end
        self._hideUis = nil
    end
end

function P:_checkUiVisible(ui)
    if not ui.activeSelf then
        return false
    end
    ui = ui.transform.parent
    while ui do
        if not ui.gameObject.activeSelf then
            return false
        end
        ui = ui.parent
    end
    return true
end

function P:_checkNext()
    local d = tpl_guide[self._data.id + 1]
    if d and d.guide == self._data.guide then
        if self._data.waitingTime then
            self._waitDt = self._data.waitingTime
            self._nextData = d
            self.Finger:SetActive(false)
            bee.setOpacity(self.Bg, 0)
            self.ImageTip:SetActive(false)
            self:hideUiTip()
        else
            self:_doNext(d)
        end
        return false
    end
    if self._data.waitingTime then
        self._waitDt = self._data.waitingTime
        self._nextData = nil
        self.Finger:SetActive(false)
        bee.setOpacity(self.Bg, 0)
        self.ImageTip:SetActive(false)
        self:hideUiTip()
        return false
    end
    return self:_doGuideEnd()
end

function P:_doGuideEnd()
	self:hideUiTip()
    if GuideManager:doGuideEnd() then
        return false
    end
    bee.emit("evt_guide_end", self._data)
    if self._RoleCamera then
        self._RoleCamera.depth = -1
    end
    CU.GameObject.Destroy(self.node)
    return true
end

function P:_doNext(d)
    self._data = d
    GuideManager:setCurGuide(d)
    print("==== ggggggg _doNext", json.encode(d))
    self:initUI(true)
    bee.logEvent("guide-id", d.id)
end

function P:_checkLog()
    if self._data.id == 4001 then
        bee.logEvent("guide-id-preview", 4001)
    end
end

function P:doClose()
	self:hideUiTip()
    CU.GameObject.Destroy(self.node)
end

function P:onBtSkip()
    bee.emit("evt_guide_skip")
end

function P:onBtClick()
    if self._isCanSkip then
        self:onBtSkip()
        return
    end
end

function P:onUpdate(dt)
    if self._waitSceneName then
        if self._waitSceneName == bee.getCurRunScene() then
            self._waitSceneName = nil
            self:_checkNext()
        end
        return
    end
    if self._waitDt then
        self._waitDt = self._waitDt - dt
        if self._waitDt <= 0 then
            self._waitDt = nil
            if not self._nextData then
                self:_doGuideEnd()
                return
            end
            self:_doNext(self._nextData)
            self._waitDt, self._nextData = nil, nil
        end
    end
    if self._tipWaitUis then
        for k, v in pairs(self._tipWaitUis) do
            if self:_checkUiVisible(v) then
                self._tipWaitUis[k] = nil
                self:addShowUiTip(v)
                self:showImageTip(false)
            end
        end
    end
end

function P:onPointerDown(e)
end

function P:onPointerUp(e)
    self:once(0.01, function()
        if self._data.kind == GuideKind.Ui then
            -- self:_checkNext()
        end
    end)
end

function P:initHollow()
    self.HollowItems.top = self:find("Top", self.Hollow):GetComponent("RectTransform")
    self.HollowItems.bottom = self:find("Bottom", self.Hollow):GetComponent("RectTransform")
    self.HollowItems.left = self:find("Left", self.Hollow):GetComponent("RectTransform")
    self.HollowItems.right = self:find("Right", self.Hollow):GetComponent("RectTransform")
    self.HollowItems.point = self:find("Point", self.Hollow).transform
    self.HollowItems.sizeDelta = UiManager:getUiRoot():GetComponent("RectTransform").sizeDelta
end
function P:setHollow(show, pos, area)
    bee.setOpacity(self.Bg, 0)
    if show then
        if not self.InitHollow then
            self.InitHollow = true
            self:initHollow()
        end
        self.Hollow:SetActive(true)
        self.HollowItems.point.position = pos
        self.HollowItems.point.localPosition = bee.v3(self.HollowItems.point.localPosition.x + area[1], self.HollowItems.point.localPosition.y + area[2], 0)
        local l = self.HollowItems.point.localPosition.x - area[3] * 0.5
        local r = self.HollowItems.point.localPosition.x + area[3] * 0.5
        local t = self.HollowItems.point.localPosition.y + area[4] * 0.5
        local b = self.HollowItems.point.localPosition.y - area[4] * 0.5
        self.HollowItems.top.offsetMin = bee.v2(self.HollowItems.sizeDelta.x * 0.5 + l, self.HollowItems.top.offsetMin.y)
        self.HollowItems.top.offsetMax = bee.v2(-(self.HollowItems.sizeDelta.x * 0.5 - r), self.HollowItems.top.offsetMax.y)
        self.HollowItems.top.sizeDelta = bee.v2(self.HollowItems.top.sizeDelta.x, self.HollowItems.sizeDelta.y * 0.5 - t)
        self.HollowItems.bottom.offsetMin = bee.v2(self.HollowItems.sizeDelta.x * 0.5 + l, self.HollowItems.bottom.offsetMin.y)
        self.HollowItems.bottom.offsetMax = bee.v2(-(self.HollowItems.sizeDelta.x * 0.5 - r), self.HollowItems.bottom.offsetMax.y)
        self.HollowItems.bottom.sizeDelta = bee.v2(self.HollowItems.top.sizeDelta.x, self.HollowItems.sizeDelta.y * 0.5 + b)
        self.HollowItems.left.offsetMin = bee.v2(self.HollowItems.left.offsetMin.x, 0)
        self.HollowItems.left.offsetMax = bee.v2(self.HollowItems.left.offsetMax.x, 0)
        self.HollowItems.left.sizeDelta = bee.v2(self.HollowItems.sizeDelta.x * 0.5 + l, self.HollowItems.left.sizeDelta.y)
        self.HollowItems.right.offsetMin = bee.v2(self.HollowItems.right.offsetMin.x, 0)
        self.HollowItems.right.offsetMax = bee.v2(self.HollowItems.right.offsetMax.x, 0)
        self.HollowItems.right.sizeDelta = bee.v2(self.HollowItems.sizeDelta.x * 0.5 - r, self.HollowItems.right.sizeDelta.y)
    else
        self.Hollow:SetActive(false)
    end
end


return P