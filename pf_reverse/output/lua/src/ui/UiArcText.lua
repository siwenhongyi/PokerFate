-- 弧形文字
local P = class("UiArcText")
UiArcText = P

-- 创建弧形文字
function P:ctor(textObj)
    self._textObj = textObj -- 文字对象
    self._text = ""
    self._vPadding = 3  -- 垂直间隔
    self._hPadding = 2  -- 水平间隔
    self._degree = 1    -- 旋转角度
    self._arcList = {}
    self._tempList = {}
end

function P:setText(text)
    if self._text ~= text then
        self._text = text
        self:_updateText()
    end
end

function P:getText()
    return self._text
end

function P:_updateText()
    self._textObj:SetActive(false)
    for _, v in ipairs(self._arcList) do
        self._tempList[#self._tempList + 1] = v
    end
    self._arcList = {}
    local n = string.utf8len(self._text)
    local w, ws, h = 0, {}, 0
    for i = 1, n do
        local s = string.utf8sub(self._text, i, 1)
        local obj = nil
        if #self._tempList > 0 then
            obj = table.remove(self._tempList, #self._tempList)
        else
            obj = CU.GameObject.Instantiate(self._textObj)
            obj.transform:SetParent(self._textObj.transform.parent, false)
            self._arcList[#self._arcList + 1] = obj
        end
        obj:SetActive(true)
        bee.setText(obj, s)
        ws[i] = CS.Utils.GetTextWidth(obj:GetComponent("Text"), s)
        w = w + ws[i]
        if i > 1 then
            w = w + self._hPadding
        end
    end
    for _, v in ipairs(self._tempList) do
        v:SetActive(false)
    end
    local pos = self._textObj.transform.localPosition
    if 1 == n then
        self._arcList[1].transform.localPosition = pos
    else
        local hs = {}
        local rs = {}
        if n > 2 then
            local n2 = math.ceil(n / 2)
            local r = n * self._degree
            if n % 2 == 0 then
                h = n2 * self._vPadding
                local y = pos.y - h / 2
                for k, v in ipairs(self._arcList) do
                    if k <= n2 then
                        hs[k] = y + (k - 1) * self._vPadding
                    elseif k > n2 then
                        hs[k] = y + (n - k) * self._vPadding
                    end
                    rs[k] = r/2 - (k - 1) * self._degree
                end
            else
                h = (n2 - 1) * self._vPadding
                local y = pos.y - h / 2
                for k, v in ipairs(self._arcList) do
                    if k <= n2 then
                        hs[k] = y + (k - 1) * self._vPadding
                    elseif k > n2 then
                        hs[k] = y + (n - k) * self._vPadding
                    end
                    rs[k] = r/2 - (k - 1) * self._degree
                end
            end
        else
            for k, v in ipairs(self._arcList) do
                hs[k] = pos.y
                rs[k] = 0
            end
        end
        local r = (n - 1) * self._degree
        local w2, h2, r2 = w / 2, h / 2, r/2
        local startPos = pos.x - w2
        for k, v in ipairs(self._arcList) do
            local x = startPos + ws[k] / 2
            local y = hs[k]
            local rate = math.abs((math.abs(x) - w2)) / w2
            y = rate * h - h2
            v.transform.localPosition = bee.v3(x, y)
            startPos = startPos + ws[k] + self._hPadding
            local a = (r2 - rate * r2) * (x >= 0 and -1 or 1)
            -- v.transform.localEulerAngles = bee.v3(0, 0, rs[k])
            v.transform.localEulerAngles = bee.v3(0, 0, a)
        end
    end
end

return P