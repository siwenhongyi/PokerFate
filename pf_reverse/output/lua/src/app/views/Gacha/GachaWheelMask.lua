local P = class("GachaWheelMask", UiBase)

-- hideCb: 结束回调 kind: 抽出的类型 1角色红 2装饰紫 3道具蓝
function P:onAwake()
    P.super.onAwake(self)

    self.ClickMask = self:find("ClickMask")
    self.SkipButton = self:find("RightTop/SkipButton")
    -- self.ClickMask:SetActive(not GuideManager:isInGuide())
    self.SkipButton:SetActive(false)

    bee.addClick(self.ClickMask, function()
        self.SkipButton:SetActive(true)
    end)
    bee.addClick(self.SkipButton, function()
        Game:playSound("ui_button_confirm")
        self:closeUI()
    end)
end

function P:onShow()
    self._kind = self._params and self._params.kind
    local name = "Red"
    if self._kind == CARD_CONTENT_TYPE.CHARACTER then
        if math.random(100) <= 5 then
            name = "purple_change"
            self:once(8.5, function()
                bee.vibrate(tpl_vibrate.shock_gacha)
            end)
        else
            self:once(8.5, function()
                bee.vibrate(tpl_vibrate.shock_gacha)
            end)
        end
    elseif self._kind == CARD_CONTENT_TYPE.DECORATION then
        name = math.random(100) <= 50 and "purple_01" or "purple_02"
    else
        name = math.random(100) <= 50 and "Blue_01" or "Blue_02"
    end
    if G_VIDEO_ERROR_MSG then
        name = "views/GachaVideo/Small/" .. name
    else
        name = "views/GachaVideo/" .. name
    end
    self._clipName = name
    self._clipObj = ObjectCache:getItemWithName(name)
    self._clipObj.transform:SetParent(self:find("AnimRoot/Center").transform, false)
    self._clipObj:SetActive(true)

    local rawImage = self._clipObj:GetComponent("RawImage")
    if bee.isNull(rawImage.texture) then
        local rt = CU.RenderTexture(2340, 1080, 0)
        rawImage.texture = rt
        self._clipObj:GetComponent("VideoPlayer").targetTexture = rt
    end

    local videoPlayer = self._clipObj:GetComponent("VideoPlayer")
    videoPlayer.time = 0
    videoPlayer:SetDirectAudioVolume(0, SettingModel:getSoundVolume())
    videoPlayer:Play()
end

function P:onHide()
end

function P:onPointerUp(e)
end

function P:evt_videoPlayerEnd()
    self:closeUI()
end

function P:closeUI()
    if not bee.isNull(self._clipObj) then
        ObjectCache:putItem(self._clipObj)
    end
    if self._params and self._params.closeCb then
        self._params.closeCb()
    end
    self:once(0.3, function()
        self:hideUI(nil, true)
    end)
end

return P