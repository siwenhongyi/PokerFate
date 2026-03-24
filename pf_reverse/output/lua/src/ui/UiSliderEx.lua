local P = class("UiSliderEx")
UiSliderEx = P

-- 扩展 Slider 控件，使它的表现变为分段式
function P:ctor(Slider)
    self.Slider = Slider
    self.FillArea = self.Slider:GetComponent("Slider").fillRect.gameObject
    self.ImageFill = bee.find("ImageFill", self.Slider)
    self.ImageHandle = bee.find("ImageHandle", self.Slider)
    self.ImageLine = bee.find("ImageLine", self.Slider)
    
    self:initSlider()
end

function P:initSlider()
    bee.addValueChanged(self.Slider, function(value)
        if self._step then
            local step = math.floor(value / self._step)
            step = math.floor((step + 1) / 2) + 1
            if self._minStep and step < self._minStep then
                step = self._minStep
                self:_setCurStep(step)
                self:refreshSlide()
            elseif self._maxStep and step > self._maxStep then
                step = self._maxStep
                self:_setCurStep(step)
                self:refreshSlide()
            end
            if step ~= self._curStep then
                self:_setCurStep(step)
                self:refreshSlide()
            elseif not self.ImageFill then
                if not self._isInSetCurStep then
                    self:refreshSlide()
                    if self._onValueChanged and not self._notNotify and self._alwaysNotify then
                        self._onValueChanged(self._datas[self._curStep], self._curStep)
                    end
                end
            end
        end
    end, "Slider")
end

function P:setEnable(enable)
    self.Slider:GetComponent("Slider").interactable = enable
end

-- 进度填充图片
function P:setImageFill(fill)
    self.ImageFill = fill
end

-- 进度位置填充图片
function P:setImageHandle(handle)
    self.ImageHandle = handle
end

function P:setImageLine(line)
    self.ImageLine = line
end

function P:onValueChanged(cb, always)
    self._onValueChanged = cb
    self._alwaysNotify = always
end

function P:setStepDatas(datas)
    self._datas = datas
    self._stepNum = #datas
    self._step = 1 / (self._stepNum * 2 - 2)
    self._curStep = 1
    
    local w = self.Slider.transform.sizeDelta.x
    local lineX = 1 / (#self._datas - 1) * w
    local handleY = self.ImageHandle and self.ImageHandle.transform.localPosition.y or 0
    local fillH = self.ImageFill and self.ImageFill.transform.sizeDelta.y or 0
    self._handleX = {bee.v3(-w/2, handleY)}
    self._sliderW = {bee.v2(0, 38)}
    local pos = bee.v3zero
    if self.ImageLine then
        self.ImageLine:SetActive(false)
        pos = self.ImageLine.transform.localPosition
    end
    local childCount = self.Slider.transform.childCount
    for i = 1, #self._datas - 2 do
        if self.ImageLine then
            local line = CU.GameObject.Instantiate(self.ImageLine, self.Slider.transform, false)
            line.transform.localPosition = bee.v3(-w / 2 + lineX * i, pos.y)
            line:SetActive(true)
            line.transform:SetSiblingIndex(3)
        end
        table.insert(self._handleX, bee.v3(-w / 2 + lineX * i, handleY))
        table.insert(self._sliderW, bee.v2(lineX * i, fillH))
    end
    table.insert(self._handleX, bee.v3(w/2, handleY))
    table.insert(self._sliderW, bee.v2(w, fillH))
end

function P:getCurData()
    return self._datas[self._curStep]
end

function P:getTotalStep()
    return self._stepNum
end

function P:getCurStep()
    return self._curStep
end

function P:setCurStep(step, notify)
    if step < 1 then
        step = 1
    elseif step > self._stepNum then
        step = self._stepNum
    end
    self._curStep = step
    self:refreshFill()
    
    self._isInSetCurStep = true
    self._notNotify = not notify
    self:refreshSlide()
    self._notNotify = nil
    self._isInSetCurStep = nil
    if notify and self._onValueChanged then
        self._onValueChanged(self._datas[self._curStep], self._curStep)
    end
end

function P:_setCurStep(step)
    self._curStep = step
    self:refreshFill()
    
    if self._onValueChanged and not self._notNotify then
        self._onValueChanged(self._datas[self._curStep], self._curStep)
    end
end

function P:setStepRange(minStep, maxStep)
    self._minStep = minStep
    self._maxStep = maxStep
end

function P:getHandlePos()
    return self._handleX[self._curStep]
end

function P:getFillSize()
    return self._sliderW[self._curStep]
end

function P:refreshFill()
    if self.ImageHandle then
        self.ImageHandle.transform.localPosition = self:getHandlePos()
    end
    if self.ImageFill then
        self.ImageFill.transform.sizeDelta = self:getFillSize()
    end
end

function P:refreshSlide()
    bee.setSliderValue(self.Slider, (self._curStep - 1) / (self._stepNum - 1), true)
end

