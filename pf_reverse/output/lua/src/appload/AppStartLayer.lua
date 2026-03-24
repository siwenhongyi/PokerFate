local P = class("AppStartLayer", UiBase)

function P:ctor()
    P.super.ctor(self)
end

function P:onAwake()
	self.Slider = self:find("Slider")
	self.Label = self:find("Label")
	self.Percent = self:find("Percent")

    if not CS.AppLoader.isReload then
        self.Slider:SetActive(true)
        self.Label:SetActive(true)
        -- self.Percent:SetActive(true)
    end
end

function P:onStart()
    self._cur = 0
    self._to = 20
end

function P:setValue(val)
    if val > 1 then val = 1 end
    bee.setSliderValue(self.Slider, val)
    bee.setText(self.Percent, tostring(math.ceil(val * 100)) .. "%")
end

function P:getMB(size)
	return math.floor(size / (1024 * 1024) * 100) / 100
end

function P:evt_load_tip(e)
    bee.setText(self.Label, e.tip)
end

function P:evt_remote_res_progress(val)
    if not self._totalNum then
        self._totalNum = CS.AppLoader.totalSize
        self._curNum = CS.AppLoader.curSize
    else
        self._curNum = CS.AppLoader.curSize
    end
    self._to = 0
    self:setValue((self._cur + val * (100 - self._cur)) / 100)
    
    if self._totalNum > 0 then
        bee.setText(self.Label, _F("LAB_LOADING_FILES", self:getMB(val * self._totalNum), tostring(self:getMB(self._totalNum)) .. "MB"))
    end
end

function P:evt_updateFinish(val)
    self._cur = 100
    self:setValue(self._cur / 100)
    bee.setText(self.Label, _T("LAB_SYSTEM_139"))
end

function P:onUpdate(dt)
    if self._cur < self._to then
        self._cur = self._cur + dt * 4
        if self._cur > self._to then
            self._cur = self._to
        end
        self:setValue(self._cur / 100)
    end
end

return P
