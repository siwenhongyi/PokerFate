-- 动态模糊 ui 基类
local P = class("UiBlurBase", UiBase)
UiBlurBase = P

function P:preShow()
	P.super.preShow(self)

	self:clearUiBlur()
end

function P:clearUiBlur()
    if self._isInBlur then
        self._isInBlur = false
        self.transform:SetParent(UiManager:getUiRoot().transform, false)
    end
    self._inBlurs = {}
end

function P:onUiBlur(flag, name, isMoveY)
    if name == self.__cname then return end
    local post = bee.find("UIRoot/UiCanvaPost")
    if not post then return end

    if flag then
        self._inBlurs[name] = name
    else
        self._inBlurs[name] = nil
    end
    
    if flag then
        if not self._isInBlur then
            self._isInBlur = true

            self.transform:SetParent(post.transform, false)
        end
        if isMoveY then
            self.transform.localPosition = bee.v3(0, -10000, 0)
        end
    else
        self:once(-1, function()
            if self._isInBlur and not next(self._inBlurs) then
                self._isInBlur = false

                self.transform:SetParent(UiManager:getUiRoot().transform, false)
                -- if isMoveY then
                    self.transform.localPosition = bee.v3zero
                -- end
            end
        end)
    end
end

