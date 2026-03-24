local P = class("LoadingLayer", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Bottom = self:find("Bottom", self.AnimRoot)

    local Loading = self:find("Loading", self.Bottom)
    self.LoadingBar = self:find("LoadingBar", Loading)
    self.LoadingEft = self:find("LoadingEft", Loading)
    self.TextDowning = self:find("TextDowning", Loading)
    self.TextPrecent = self:find("TextPrecent", Loading)

    self.LoadingEftPos = self.LoadingEft.transform.localPosition

    self.RightTop = self:find("RightTop", self.AnimRoot)
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
                end
            else
                self:hideUI()
            end
        end
    end)
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

