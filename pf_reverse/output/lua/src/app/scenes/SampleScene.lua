local P = class("SampleScene", UiScene)

function P:ctor()
    local Button = bee.find("Canvas/Button")
    local Image = bee.find("Canvas/Image")
    local Icon = bee.find("Canvas/Icon")
    local cmp = Image:GetComponent("BezierPoint")
    bee.addClick(Button, function()
        if cmp then
            cmp:StartBezierAction(Icon, 1)
        end
    end)
end

return P
