local P = class("LoadingLayer", UiBase)

function P:onAwake()
    self.inPop = true
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.Bottom = self:find("Bottom", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)

    self.LoadingImg = self:find("LoadingImg", self.Center)

    local Loading = self:find("Loading", self.Bottom)
    self.LoadingBar = self:find("LoadingBar", Loading)
    self.LoadingEft = self:find("LoadingEft", Loading)
    self.TextDowning = self:find("TextDowning", Loading)
    self.TextPrecent = self:find("TextPrecent", Loading)

    self.LoadingEftPos = self.LoadingEft.transform.localPosition

    self.RightTop = self:find("RightTop", self.AnimRoot)

    self:evt_refreshLimitView()
end

function P:onShow()
    local dt = self._params and self._params.dt or 1

    bee.Tween.toFloat(0, 1, dt, function(val)
        self:setProgress(val)
        if val >= 1 then
            if self._params and self._params.cb then
                if not self._isEnded then
                    self._isEnded = true
                    self._params.cb()
                    self:once(2, function()     -- 2秒后自动关闭，防卡死
                        self:hideUI()
                    end)
                end
            else
                self:hideUI()
            end
        end
    end)

    bee.emit(EventDef.evt_loading_show)

    local isUseKv2 = tpl_constdata.KV2_Endtime > bee.getServerTime()
    self:find("LogoIcon", self.LeftTop):SetActive(not isUseKv2)
    self:find("LogoIcon2", self.LeftTop):SetActive(isUseKv2)
end

function P:onDestroy()
    P.super.onDestroy(self)
    bee.emit(EventDef.evt_loading_hide)
end

function P:setDownloadText(text)
    self._downloadText = text
    bee.setText(self.TextDowning, _T(text))
end

function P:setProgress(val)
    self.Bottom:SetActive(true)
    
    self._downloadText = nil
    bee.setText(self.TextPrecent, tostring(math.ceil(val * 100)) .. "%")
    bee.setFillAmount(self.LoadingBar, val)
    local pos = bee.v3(self.LoadingEftPos.x * 2 * val - self.LoadingEftPos.x, self.LoadingEftPos.y)
    self.LoadingEft.transform.localPosition = pos
end

function P:evt_refreshLimitView()
    local propCfg = tpl_props[PlayerModel:getIllustrationId()]
    GF.setIllustrationImage(propCfg.mapId, self.LoadingImg, true)
end

return P