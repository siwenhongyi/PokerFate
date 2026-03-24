local P = class("UiSliderEx2", UiSliderEx)
UiSliderEx2 = P

-- 双滑块的分段 Slider
function P:ctor(Slider)
    P.super.ctor(self, Slider)
    self.ImageHandle2 = bee.find("ImageHandle2", self.Slider)
    self._stepIdx = 1
end

function P:initSlider()
    local value, isActive = nil, false
    bee.addValueChanged(self.Slider, function(v)
        if self._step then
            if isActive then
                self:__setValue(v)
                value = nil
            else
                value = v
            end
        end
    end, "Slider")

    local ex = self.Slider:AddComponent(typeof(CS.UiSliderEx))
    ex:SetOnPointDown(function(kind)
        if 0 == kind then
            local ret, p = CU.RectTransformUtility.ScreenPointToLocalPointInRectangle(self.Slider.transform, ex.downPoint.pressPosition, CU.Camera.main)
            local p1, p2 = self.ImageHandle.transform.localPosition, self.ImageHandle2.transform.localPosition
            if p.x <= p1.x then
                self._stepIdx = 1
            elseif p.x >= p2.x then
                self._stepIdx = 2
            elseif math.abs(p.x - p1.x) < math.abs(p.x - p2.x) then
                self._stepIdx = 1
            else
                self._stepIdx = 2
            end
            isActive = true
            if value then
                self:__setValue(value)
            end
        else
            isActive = false
            value = nil
        end
    end)
end

function P:__setValue(value)
    local step = math.floor(value / self._step)
    step = math.floor((step + 1) / 2) + 1
    if self._curStep == self._curStep2 then
        if step ~= self._curStep then
            if step < self._curStep then
                self:_setStep(step, self._curStep2)
                self._stepIdx = 1
            else
                self:_setStep(self._curStep, step)
                self._stepIdx = 2
            end
        end
    else
        if self._stepIdx == 1 and step ~= self._curStep then
            self:_setStep(step, self._curStep2)
        elseif self._stepIdx == 2 and step ~= self._curStep2 then
            self:_setStep(self._curStep, step)
        end
    end
end

function P:setImageHandle2(handle)
    self.ImageHandle2 = handle
end

function P:setStep(step1, step2)
    if step1 < 1 then
        step1 = 1
    elseif step1 > self._stepNum then
        step1 = self._stepNum
    end
    if step2 < 1 then
        step2 = 1
    elseif step2 > self._stepNum then
        step2 = self._stepNum
    end
    if step1 > step2 then
        step1, step2 = step2, step1
    end
    self:_setStep(step1, step2)
end

function P:_setStep(step1, step2)
    self._curStep = step1
    self._curStep2 = step2
    self:refreshFill()
    if self._onValueChanged then
        self._onValueChanged(self._datas[self._curStep], self._datas[self._curStep2])
    end
end

function P:getCurStep2()
    return self._curStep2
end

function P:refreshFill()
    if self.ImageHandle then
        self.ImageHandle.transform.localPosition = self._handleX[self._curStep]
    end
    if self.ImageHandle2 then
        self.ImageHandle2.transform.localPosition = self._handleX[self._curStep2]
    end
    if self.ImageFill then
        self.ImageFill.transform.localPosition = bee.v3(self._handleX[self._curStep].x, self.ImageFill.transform.localPosition.y)
        self.ImageFill.transform.sizeDelta = bee.v2(self._sliderW[self._curStep2].x - self._sliderW[self._curStep].x, self._sliderW[self._curStep2].y)
    end
end

